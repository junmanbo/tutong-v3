"""Rebalancing 봇 Celery Worker.

전략:
  - 다자산 포트폴리오의 목표 비중 설정
  - 주기적(interval_seconds)으로 현재 비중과 목표 비중 비교
  - 비중 차이가 임계값(threshold_pct) 초과 시 리밸런싱 주문 실행
  - 매도 먼저 실행 (quote 확보) → 매수 실행

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
    _update_bot_status_running,
    _update_bot_status_stopped,
    clear_stop_signal,
    should_stop,
)

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=AsyncBotTask,
    name="bot_engine.workers.rebalancing.run",
    max_retries=0,
    acks_late=True,
)
def run_rebalancing(self, *, bot_id: str) -> None:
    """Rebalancing 봇 실행 Task."""

    async def _run() -> None:
        from sqlmodel import Session, create_engine, select

        from app.core.config import settings
        from app.exchange_adapters.base import OrderRequest
        from app.models import Bot, ExchangeAccount
        from bot_engine.exchange_adapters import get_adapter
        from bot_engine.strategies.rebalancing import (
            RebalancingConfig,
            calc_rebalance_orders,
            calc_weights,
            needs_rebalance,
        )
        from bot_engine.utils.crypto import decrypt
        from bot_engine.utils.decimal_utils import apply_lot_size, to_decimal

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
            bot_config = bot.config or {}
            exchange = account.exchange

        # ── 설정 파싱 ────────────────────────────────────────────────────────
        config = RebalancingConfig.from_dict(bot_config)
        quote = config.quote

        adapter = get_adapter(
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret,
            extra_params=extra_params,
        )

        _update_bot_status_running(bot_id=bot_id, celery_task_id=self.request.id)
        logger.info(
            "Rebalancing bot started: bot_id=%s assets=%s threshold=%s interval=%ds",
            bot_id, list(config.assets.keys()), config.threshold_pct, config.interval_seconds,
        )

        try:
            while True:
                if should_stop(bot_id):
                    logger.info("Stop signal received: bot_id=%s", bot_id)
                    clear_stop_signal(bot_id)
                    break

                try:
                    # 잔고 및 현재가 조회
                    balance_items = await adapter.get_balance()
                    balances: dict[str, Decimal] = {
                        item.asset: item.free for item in balance_items
                        if item.asset in config.assets
                    }

                    # 목표 자산 중 잔고에 없는 것은 0으로 초기화
                    for asset in config.assets:
                        if asset not in balances:
                            balances[asset] = Decimal("0")

                    # 가격 조회 (quote 제외한 자산)
                    prices: dict[str, Decimal] = {}
                    for asset in config.assets:
                        if asset == quote:
                            continue
                        try:
                            ticker = await adapter.get_ticker(f"{asset}/{quote}")
                            prices[asset] = ticker.last
                        except Exception as exc:
                            logger.warning(
                                "Failed to get ticker for %s/%s: %s", asset, quote, exc
                            )

                    # 비중 계산
                    current_weights = calc_weights(balances, prices, quote)
                    total_value = sum(
                        (balances[asset] * prices.get(asset, Decimal("1"))
                         if asset != quote else balances[asset])
                        for asset in balances
                    )

                    logger.debug(
                        "Rebalancing check: bot_id=%s weights=%s total=%s",
                        bot_id,
                        {k: f"{v:.1f}%" for k, v in current_weights.items()},
                        total_value,
                    )

                    if needs_rebalance(current_weights, config.assets, config.threshold_pct):
                        orders = calc_rebalance_orders(
                            current_weights, config.assets, total_value, quote
                        )
                        logger.info(
                            "Rebalancing triggered: bot_id=%s orders=%d",
                            bot_id, len(orders),
                        )
                        for rb_order in orders:
                            if rb_order.asset not in prices:
                                continue
                            price = prices[rb_order.asset]
                            if price <= Decimal("0"):
                                continue
                            qty = apply_lot_size(
                                rb_order.amount / price, bot_config.get("step_size", "0.00001")
                            )
                            if qty <= Decimal("0"):
                                continue
                            try:
                                order = await adapter.place_order(
                                    OrderRequest(
                                        symbol=f"{rb_order.asset}/{quote}",
                                        side=rb_order.side,
                                        order_type="market",
                                        quantity=qty,
                                    )
                                )
                                logger.info(
                                    "Rebalance order: %s %s %s @ %s order_id=%s",
                                    rb_order.side, qty, rb_order.asset,
                                    price, order.order_id,
                                )
                            except Exception as exc:
                                logger.error(
                                    "Rebalance order error: asset=%s side=%s error=%s",
                                    rb_order.asset, rb_order.side, exc,
                                )

                except Exception as exc:
                    logger.error("Rebalancing check error: bot_id=%s error=%s", bot_id, exc)

                # 1분 단위로 stop 신호 확인
                await asyncio.sleep(min(config.interval_seconds, 60))

        finally:
            await adapter.close()

        _update_bot_status_stopped(bot_id=bot_id)
        logger.info("Rebalancing bot stopped: bot_id=%s", bot_id)

    self.run_async(_run())
