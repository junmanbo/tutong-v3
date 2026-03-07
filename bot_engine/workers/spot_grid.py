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
from decimal import Decimal

from bot_engine.celery_app import celery_app
from bot_engine.workers.base import (
    AsyncBotTask,
    _create_bot_log,
    _update_bot_status_completed,
    _update_bot_status_running,
    _update_bot_status_stopped,
    _update_bot_total_pnl_pct,
    calc_change_pct,
    clear_stop_signal,
    evaluate_risk_limits,
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
        from sqlmodel import select

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
        with _get_db_session() as session:
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
            symbol = bot.symbol or "BTC/KRW"
            bot_config = bot.config or {}
            exchange = account.exchange
            stop_loss_pct = bot.stop_loss_pct
            take_profit_pct = bot.take_profit_pct

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
        _create_bot_log(
            bot_id=bot_id,
            event_type="grid_started",
            level="info",
            message="Spot Grid bot started",
            payload={"symbol": symbol, "grid_count": config.grid_count},
        )

        # ── 그리드 초기화 ────────────────────────────────────────────────────
        r = get_redis()
        state_key = f"bot:{bot_id}:grid_state"
        risk_key = f"bot:{bot_id}:grid_risk"
        risk_raw = r.get(risk_key)
        risk_state: dict = json.loads(risk_raw) if risk_raw else {}
        initial_price: Decimal | None = None
        if risk_state.get("initial_price"):
            initial_price = Decimal(risk_state["initial_price"])
        final_status = "stopped"
        final_reason: str | None = None

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
            current_price = ticker.price
            if initial_price is None and current_price > Decimal("0"):
                initial_price = current_price
                r.set(risk_key, json.dumps({"initial_price": str(initial_price)}))

            for level in levels:
                if level.price < current_price:  # 현재가 이하 레벨만 매수 주문
                    try:
                        order = await adapter.place_order(
                            OrderRequest(
                                symbol=symbol,
                                side="buy",
                                order_type="limit",
                                qty=level.qty,
                                price=level.price,
                            )
                        )
                        level.order_id = order.exchange_order_id
                        logger.debug(
                            "Grid buy order placed: price=%s qty=%s order_id=%s",
                            level.price, level.qty, order.exchange_order_id,
                        )
                        _create_bot_log(
                            bot_id=bot_id,
                            event_type="order_placed",
                            level="info",
                            message="Grid initial buy order placed",
                            payload={
                                "side": "buy",
                                "price": str(level.price),
                                "qty": str(level.qty),
                                "order_id": order.exchange_order_id,
                            },
                        )
                    except Exception as exc:
                        logger.error(
                            "Failed to place grid order: price=%s error=%s",
                            level.price, exc,
                        )
                        _create_bot_log(
                            bot_id=bot_id,
                            event_type="order_error",
                            level="error",
                            message=f"Grid initial buy order error: {exc}",
                            payload={"price": str(level.price)},
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

                try:
                    ticker = await adapter.get_ticker(symbol)
                    current_price = ticker.price
                    if initial_price is None and current_price > Decimal("0"):
                        initial_price = current_price
                        r.set(risk_key, json.dumps({"initial_price": str(initial_price)}))
                    if initial_price is not None:
                        pnl_pct = calc_change_pct(current_price, initial_price)
                        _update_bot_total_pnl_pct(bot_id=bot_id, pnl_pct=pnl_pct)
                        risk = evaluate_risk_limits(
                            change_pct=pnl_pct,
                            stop_loss_pct=stop_loss_pct,
                            take_profit_pct=take_profit_pct,
                        )
                        if risk:
                            final_status, final_reason = risk
                            logger.info(
                                "Grid auto-stop: bot_id=%s reason=%s",
                                bot_id,
                                final_reason,
                            )
                            break
                except Exception as exc:
                    logger.warning("Grid ticker read failed: bot_id=%s error=%s", bot_id, exc)

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
                            _create_bot_log(
                                bot_id=bot_id,
                                event_type="order_filled",
                                level="info",
                                message="Grid order filled",
                                payload={
                                    "side": level.side,
                                    "price": str(level.price),
                                    "qty": str(level.qty),
                                    "order_id": level.order_id,
                                },
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
                                                qty=new_level.qty,
                                                price=new_level.price,
                                            )
                                        )
                                        new_level.order_id = order.exchange_order_id
                                        _create_bot_log(
                                            bot_id=bot_id,
                                            event_type="counter_order_placed",
                                            level="info",
                                            message="Grid counter sell order placed",
                                            payload={
                                                "side": "sell",
                                                "price": str(new_level.price),
                                                "qty": str(new_level.qty),
                                                "order_id": order.exchange_order_id,
                                            },
                                        )
                                    except Exception as exc:
                                        logger.error(
                                            "Failed to place counter sell: price=%s error=%s",
                                            new_level.price, exc,
                                        )
                                        _create_bot_log(
                                            bot_id=bot_id,
                                            event_type="order_error",
                                            level="error",
                                            message=f"Counter sell order error: {exc}",
                                            payload={"price": str(new_level.price)},
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
                                                qty=new_level.qty,
                                                price=new_level.price,
                                            )
                                        )
                                        new_level.order_id = order.exchange_order_id
                                        _create_bot_log(
                                            bot_id=bot_id,
                                            event_type="counter_order_placed",
                                            level="info",
                                            message="Grid counter buy order placed",
                                            payload={
                                                "side": "buy",
                                                "price": str(new_level.price),
                                                "qty": str(new_level.qty),
                                                "order_id": order.exchange_order_id,
                                            },
                                        )
                                    except Exception as exc:
                                        logger.error(
                                            "Failed to place counter buy: price=%s error=%s",
                                            new_level.price, exc,
                                        )
                                        _create_bot_log(
                                            bot_id=bot_id,
                                            event_type="order_error",
                                            level="error",
                                            message=f"Counter buy order error: {exc}",
                                            payload={"price": str(new_level.price)},
                                        )

                    except Exception as exc:
                        logger.error(
                            "Error polling order: order_id=%s error=%s",
                            level.order_id, exc,
                        )
                        _create_bot_log(
                            bot_id=bot_id,
                            event_type="order_poll_error",
                            level="error",
                            message=f"Order polling error: {exc}",
                            payload={"order_id": level.order_id},
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
            r.delete(risk_key)

        if final_status == "completed":
            _update_bot_status_completed(bot_id=bot_id, reason=final_reason)
        else:
            _update_bot_status_stopped(bot_id=bot_id, reason=final_reason)
        logger.info("Spot Grid bot stopped: bot_id=%s", bot_id)

    self.run_async(_run())
