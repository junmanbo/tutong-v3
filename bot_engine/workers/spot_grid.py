"""Spot Grid 봇 Celery Worker.

전략:
  - 상한가(upper)와 하한가(lower) 사이를 grid_count 개의 구간으로 분할
  - 각 그리드 레벨에 지정가 매수 주문을 배치
  - 매수 체결 → 바로 위 레벨에 지정가 매도 주문 배치
  - 매도 체결 → 바로 아래 레벨에 지정가 매수 주문 재배치

Redis 정지 신호: redis.set(f"bot:{bot_id}:stop", "1")
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict

from bot_engine.celery_app import celery_app
from bot_engine.workers.base import (
    AsyncBotTask,
    _update_bot_status_running,
    _update_bot_status_stopped,
    clear_stop_signal,
    get_redis,
    should_stop,
)

logger = logging.getLogger(__name__)

# 체결 확인 폴링 주기 (초)
_POLL_INTERVAL = 30


@celery_app.task(
    bind=True,
    base=AsyncBotTask,
    name="bot_engine.workers.spot_grid.run",
    max_retries=0,
    acks_late=True,
)
def run_spot_grid(self, *, bot_id: str) -> None:
    """Spot Grid 봇 실행 Task."""

    async def _run() -> None:
        from decimal import Decimal

        from sqlmodel import Session, create_engine, select

        from app.core.config import settings
        from app.exchange_adapters.base import OrderRequest
        from app.models import Bot, ExchangeAccount
        from bot_engine.exchange_adapters import get_adapter
        from bot_engine.strategies.spot_grid import (
            GridConfig,
            GridLevel,
            build_grid,
            on_buy_filled,
            on_sell_filled,
        )
        from bot_engine.utils.crypto import decrypt
        from bot_engine.utils.decimal_utils import to_decimal

        # ── DB에서 봇/계좌 정보 로드 ────────────────────────────────────────
        engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
        with Session(engine) as session:
            bot = session.exec(
                select(Bot).where(Bot.id == uuid.UUID(bot_id))
            ).first()
            if not bot:
                logger.error("Bot not found: %s", bot_id)
                return

            account = session.exec(
                select(ExchangeAccount).where(ExchangeAccount.id == bot.account_id)
            ).first()
            if not account:
                logger.error("Account not found for bot: %s", bot_id)
                return

            api_key = decrypt(account.api_key_enc, settings.ENCRYPTION_KEY)
            api_secret = decrypt(account.api_secret_enc, settings.ENCRYPTION_KEY)
            extra_params: dict | None = None
            if account.extra_params_enc:
                extra_params = json.loads(
                    decrypt(account.extra_params_enc, settings.ENCRYPTION_KEY)
                )
            symbol = bot.symbol or "BTC/USDT"
            bot_config = bot.config or {}
            exchange = account.exchange

        # ── 설정 파싱 ────────────────────────────────────────────────────────
        config = GridConfig.from_dict(symbol, bot_config)

        adapter = get_adapter(
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret,
            extra_params=extra_params,
        )

        _update_bot_status_running(bot_id=bot_id, celery_task_id=self.request.id)
        logger.info(
            "Spot Grid bot started: bot_id=%s symbol=%s grid_count=%d",
            bot_id, symbol, config.grid_count,
        )

        # ── 그리드 초기화 ────────────────────────────────────────────────────
        r = get_redis()
        state_key = f"bot:{bot_id}:grid_state"

        # 기존 상태 복원 또는 새 그리드 생성
        state_raw = r.get(state_key)
        if state_raw:
            # 재시작: 이전 그리드 상태 복원
            raw_levels: list[dict] = json.loads(state_raw)
            levels: list[GridLevel] = [
                GridLevel(
                    price=to_decimal(lv["price"]),
                    qty=to_decimal(lv["qty"]),
                    side=lv["side"],
                    order_id=lv.get("order_id"),
                    filled=lv.get("filled", False),
                )
                for lv in raw_levels
            ]
            logger.info("Grid state restored: bot_id=%s levels=%d", bot_id, len(levels))
        else:
            # 신규 시작: 그리드 초기화 및 초기 매수 주문 배치
            levels = build_grid(config)
            ticker = await adapter.get_ticker(symbol)
            current_price = ticker.last

            for level in levels:
                if level.price < current_price:  # 현재가 이하 레벨만 매수 주문
                    try:
                        order = await adapter.place_order(
                            OrderRequest(
                                symbol=symbol,
                                side="buy",
                                order_type="limit",
                                quantity=level.qty,
                                price=level.price,
                            )
                        )
                        level.order_id = order.order_id
                        logger.debug(
                            "Grid buy order placed: price=%s qty=%s order_id=%s",
                            level.price, level.qty, order.order_id,
                        )
                    except Exception as exc:
                        logger.error(
                            "Failed to place grid order: price=%s error=%s",
                            level.price, exc,
                        )

            # 상태 저장
            r.set(state_key, json.dumps([
                {
                    "price": str(lv.price),
                    "qty": str(lv.qty),
                    "side": lv.side,
                    "order_id": lv.order_id,
                    "filled": lv.filled,
                }
                for lv in levels
            ]))
            logger.info(
                "Grid initialized: bot_id=%s levels=%d current_price=%s",
                bot_id, len(levels), current_price,
            )

        try:
            # ── 메인 루프: 체결 확인 폴링 ───────────────────────────────────
            while True:
                if should_stop(bot_id):
                    logger.info("Stop signal received: bot_id=%s", bot_id)
                    clear_stop_signal(bot_id)
                    break

                # 미체결 주문 폴링
                for level in list(levels):
                    if level.order_id is None or level.filled:
                        continue
                    try:
                        order_status = await adapter.get_order(level.order_id, symbol)
                        if order_status.status == "closed":
                            logger.info(
                                "Grid order filled: side=%s price=%s qty=%s",
                                level.side, level.price, level.qty,
                            )
                            if level.side == "buy":
                                new_level = on_buy_filled(level, levels)
                                if new_level:
                                    try:
                                        order = await adapter.place_order(
                                            OrderRequest(
                                                symbol=symbol,
                                                side="sell",
                                                order_type="limit",
                                                quantity=new_level.qty,
                                                price=new_level.price,
                                            )
                                        )
                                        new_level.order_id = order.order_id
                                    except Exception as exc:
                                        logger.error(
                                            "Failed to place counter sell: price=%s error=%s",
                                            new_level.price, exc,
                                        )
                            else:  # sell filled
                                new_level = on_sell_filled(level, levels)
                                if new_level:
                                    try:
                                        order = await adapter.place_order(
                                            OrderRequest(
                                                symbol=symbol,
                                                side="buy",
                                                order_type="limit",
                                                quantity=new_level.qty,
                                                price=new_level.price,
                                            )
                                        )
                                        new_level.order_id = order.order_id
                                    except Exception as exc:
                                        logger.error(
                                            "Failed to place counter buy: price=%s error=%s",
                                            new_level.price, exc,
                                        )

                    except Exception as exc:
                        logger.error(
                            "Error polling order: order_id=%s error=%s",
                            level.order_id, exc,
                        )

                # 상태 저장
                r.set(state_key, json.dumps([
                    {
                        "price": str(lv.price),
                        "qty": str(lv.qty),
                        "side": lv.side,
                        "order_id": lv.order_id,
                        "filled": lv.filled,
                    }
                    for lv in levels
                ]))

                await asyncio.sleep(_POLL_INTERVAL)

        finally:
            await adapter.close()
            r.delete(state_key)

        _update_bot_status_stopped(bot_id=bot_id)
        logger.info("Spot Grid bot stopped: bot_id=%s", bot_id)

    self.run_async(_run())
