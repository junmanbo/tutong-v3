"""Spot DCA (Dollar-Cost Averaging) 봇 Celery Worker.

전략:
  - 정해진 주기(interval_seconds)마다 정액(amount_per_order) 자동 매수
  - 시장가 또는 지정가 주문
  - 장기 적립식 매수로 평균 매입가 분산

Redis 정지 신호: redis.set(f"bot:{bot_id}:stop", "1")
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from bot_engine.celery_app import celery_app
from bot_engine.workers.base import (
    AsyncBotTask,
    _cancel_open_orders_for_bot,
    _create_bot_log,
    _get_db_session,
    _record_order_and_trade,
    _resolve_order_fill,
    _update_bot_status_completed,
    _update_bot_status_running,
    _update_bot_status_stopped,
    _update_bot_total_pnl_pct,
    calc_change_pct,
    clear_cancel_open_orders_flag,
    clear_stop_signal,
    evaluate_risk_limits,
    get_redis,
    should_cancel_open_orders,
    should_stop,
)

logger = logging.getLogger(__name__)
UTC = timezone.utc


@celery_app.task(
    bind=True,
    base=AsyncBotTask,
    name="bot_engine.workers.spot_dca.run",
    max_retries=0,
    acks_late=True,
)
def run_spot_dca(self, *, bot_id: str) -> None:
    """Spot DCA 봇 실행 Task."""

    async def _run() -> None:
        from decimal import Decimal

        from sqlmodel import select

        from app.core.config import settings
        from app.exchange_adapters.base import OrderRequest
        from app.models import Bot, ExchangeAccount
        from bot_engine.exchange_adapters import get_adapter
        from bot_engine.strategies.spot_dca import (
            DcaConfig,
            calc_order_qty,
            is_completed,
            should_buy,
        )
        from bot_engine.utils.crypto import decrypt

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
        config = DcaConfig.from_dict(symbol, bot_config)

        # ── 어댑터 생성 ──────────────────────────────────────────────────────
        adapter = get_adapter(
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret,
            extra_params=extra_params,
        )

        _update_bot_status_running(bot_id=bot_id, celery_task_id=self.request.id)
        logger.info(
            "Spot DCA bot started: bot_id=%s symbol=%s interval=%ds amount=%s",
            bot_id, symbol, config.interval_seconds, config.amount_per_order,
        )
        _create_bot_log(
            bot_id=bot_id,
            event_type="dca_started",
            level="info",
            message="Spot DCA bot started",
            payload={
                "symbol": symbol,
                "interval_seconds": config.interval_seconds,
                "amount_per_order": str(config.amount_per_order),
            },
        )

        # ── Redis에서 이전 상태 복원 ─────────────────────────────────────────
        r = get_redis()
        state_key = f"bot:{bot_id}:dca_state"
        state_raw = r.get(state_key)
        state: dict = json.loads(state_raw) if state_raw else {}
        order_count: int = state.get("order_count", 0)
        initial_price: Decimal | None = None
        if state.get("initial_price"):
            initial_price = Decimal(state["initial_price"])
        last_order_time: datetime | None = None
        if state.get("last_order_time"):
            last_order_time = datetime.fromisoformat(state["last_order_time"])

        final_status = "stopped"
        final_reason: str | None = None

        try:
            while True:
                if should_stop(bot_id):
                    logger.info("Stop signal received: bot_id=%s", bot_id)
                    if should_cancel_open_orders(bot_id):
                        canceled_count = await _cancel_open_orders_for_bot(
                            bot_id=bot_id,
                            adapter=adapter,
                        )
                        logger.info(
                            "Open orders canceled on stop: bot_id=%s canceled=%d",
                            bot_id,
                            canceled_count,
                        )
                    clear_stop_signal(bot_id)
                    clear_cancel_open_orders_flag(bot_id)
                    break

                if is_completed(order_count, config.total_orders):
                    logger.info(
                        "DCA completed: bot_id=%s total_orders=%d",
                        bot_id, config.total_orders,
                    )
                    final_status = "completed"
                    final_reason = "DCA total orders completed"
                    _create_bot_log(
                        bot_id=bot_id,
                        event_type="dca_completed",
                        level="info",
                        message=final_reason,
                        payload={"order_count": order_count},
                    )
                    break

                now = datetime.now(UTC)
                if should_buy(last_order_time, config.interval_seconds, now):
                    try:
                        ticker = await adapter.get_ticker(symbol)
                        price = ticker.price
                        if initial_price is None and price > Decimal("0"):
                            initial_price = price

                        if initial_price is not None:
                            pnl_pct = calc_change_pct(price, initial_price)
                            _update_bot_total_pnl_pct(bot_id=bot_id, pnl_pct=pnl_pct)
                            risk = evaluate_risk_limits(
                                change_pct=pnl_pct,
                                stop_loss_pct=stop_loss_pct,
                                take_profit_pct=take_profit_pct,
                            )
                            if risk:
                                final_status, final_reason = risk
                                logger.info(
                                    "DCA auto-stop: bot_id=%s reason=%s",
                                    bot_id,
                                    final_reason,
                                )
                                _create_bot_log(
                                    bot_id=bot_id,
                                    event_type="risk_triggered",
                                    level="warning",
                                    message=final_reason,
                                    payload={"change_pct": str(pnl_pct)},
                                )
                                break

                        qty = calc_order_qty(config.amount_per_order, price, config.step_size)

                        if qty <= Decimal("0"):
                            logger.warning(
                                "Calculated qty is zero: bot_id=%s price=%s amount=%s",
                                bot_id, price, config.amount_per_order,
                            )
                        else:
                            exchange_name = str(getattr(exchange, "value", exchange)).lower()
                            if config.order_type == "market" and exchange_name == "upbit":
                                # Upbit market buy는 수량이 아니라 KRW 금액(cost) 기준
                                request = OrderRequest(
                                    symbol=symbol,
                                    side="buy",
                                    order_type=config.order_type,
                                    amount=config.amount_per_order,
                                )
                            else:
                                request = OrderRequest(
                                    symbol=symbol,
                                    side="buy",
                                    order_type=config.order_type,
                                    qty=qty,
                                )

                            order = await adapter.place_order(request)
                            resolved_order = await _resolve_order_fill(
                                adapter=adapter,
                                order=order,
                                symbol=symbol,
                            )
                            _record_order_and_trade(
                                bot_id=bot_id,
                                order=resolved_order,
                                qty_hint=qty,
                                price_hint=price,
                            )
                            order_count += 1
                            last_order_time = now
                            r.set(
                                state_key,
                                json.dumps({
                                    "order_count": order_count,
                                    "initial_price": str(initial_price) if initial_price else None,
                                    "last_order_time": now.isoformat(),
                                }),
                            )
                            logger.info(
                                "DCA order placed: bot_id=%s #%d order_id=%s qty=%s price=%s",
                                bot_id, order_count, order.exchange_order_id, qty, price,
                            )
                            _create_bot_log(
                                bot_id=bot_id,
                                event_type="order_placed",
                                level="info",
                                message="DCA buy order placed",
                                payload={
                                    "order_count": order_count,
                                    "order_id": order.exchange_order_id,
                                    "qty": str(qty),
                                    "price": str(price),
                                },
                            )
                    except Exception as exc:
                        logger.error("DCA order error: bot_id=%s error=%s", bot_id, exc)
                        _create_bot_log(
                            bot_id=bot_id,
                            event_type="order_error",
                            level="error",
                            message=f"DCA order error: {exc}",
                        )

                # 1분 단위로 stop 신호 확인 (interval이 길어도 빠른 정지 보장)
                await asyncio.sleep(min(config.interval_seconds, 60))

        finally:
            await adapter.close()
            r.delete(state_key)

        if final_status == "completed":
            _update_bot_status_completed(bot_id=bot_id, reason=final_reason)
        else:
            _update_bot_status_stopped(bot_id=bot_id, reason=final_reason)
        logger.info("Spot DCA bot stopped: bot_id=%s total_orders=%d", bot_id, order_count)

    self.run_async(_run())
