"""Algo Orders (TWAP) 봇 Celery Worker.

전략:
  - TWAP(Time-Weighted Average Price): 대량 주문을 시간 가중 평균가로 분할 실행
  - 지정된 시간(duration_seconds) 동안 num_slices개로 균등 분할
  - 각 슬라이스는 total_qty / num_slices 수량, 마지막 슬라이스는 잔여 수량
  - 모든 슬라이스 완료 시 봇 자동 종료

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


@celery_app.task(
    bind=True,
    base=AsyncBotTask,
    name="bot_engine.workers.algo_orders.run",
    max_retries=0,
    acks_late=True,
)
def run_algo_orders(self, *, bot_id: str) -> None:
    """Algo Orders (TWAP) 봇 실행 Task."""

    async def _run() -> None:
        from sqlmodel import select

        from app.core.config import settings
        from app.exchange_adapters.base import OrderRequest
        from app.models import Bot, ExchangeAccount
        from bot_engine.exchange_adapters import get_adapter
        from bot_engine.strategies.algo_orders import (
            AlgoConfig,
            calc_interval,
            calc_remaining_qty,
            calc_slice_qty,
            is_completed,
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
        config = AlgoConfig.from_dict(symbol, bot_config)
        slice_qty = calc_slice_qty(config.total_qty, config.num_slices, config.step_size)
        interval_sec = calc_interval(config.duration_seconds, config.num_slices)

        adapter = get_adapter(
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret,
            extra_params=extra_params,
        )

        _update_bot_status_running(bot_id=bot_id, celery_task_id=self.request.id)
        logger.info(
            "Algo Orders bot started: bot_id=%s symbol=%s side=%s total=%s "
            "slices=%d slice_qty=%s interval=%ds",
            bot_id, symbol, config.side, config.total_qty,
            config.num_slices, slice_qty, interval_sec,
        )
        _create_bot_log(
            bot_id=bot_id,
            event_type="algo_started",
            level="info",
            message="Algo Orders bot started",
            payload={
                "symbol": symbol,
                "side": config.side,
                "num_slices": config.num_slices,
                "interval_sec": interval_sec,
            },
        )

        # ── Redis에서 이전 상태 복원 ─────────────────────────────────────────
        r = get_redis()
        state_key = f"bot:{bot_id}:algo_state"
        state_raw = r.get(state_key)
        executed_slices: int = json.loads(state_raw).get("executed_slices", 0) if state_raw else 0
        initial_price: Decimal | None = None
        if state_raw:
            state = json.loads(state_raw)
            if state.get("initial_price"):
                initial_price = Decimal(state["initial_price"])

        final_status = "stopped"
        final_reason: str | None = None

        try:
            while True:
                if should_stop(bot_id):
                    logger.info("Stop signal received: bot_id=%s", bot_id)
                    clear_stop_signal(bot_id)
                    break

                if is_completed(executed_slices, config.num_slices):
                    logger.info(
                        "Algo Orders completed: bot_id=%s slices=%d/%d",
                        bot_id, executed_slices, config.num_slices,
                    )
                    final_status = "completed"
                    final_reason = "TWAP slices completed"
                    _create_bot_log(
                        bot_id=bot_id,
                        event_type="algo_completed",
                        level="info",
                        message=final_reason,
                        payload={"executed_slices": executed_slices},
                    )
                    break

                try:
                    ticker = await adapter.get_ticker(symbol)
                    current_price = ticker.price
                    if initial_price is None and current_price > Decimal("0"):
                        initial_price = current_price
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
                                "Algo auto-stop: bot_id=%s reason=%s",
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
                except Exception as exc:
                    logger.warning("Algo ticker read failed: bot_id=%s error=%s", bot_id, exc)

                # 마지막 슬라이스는 잔여 수량 사용
                is_last = (executed_slices == config.num_slices - 1)
                qty = (
                    calc_remaining_qty(
                        config.total_qty, slice_qty, executed_slices, config.step_size
                    )
                    if is_last
                    else slice_qty
                )

                if qty <= Decimal("0"):
                    logger.warning(
                        "Slice qty is zero: bot_id=%s slice=%d", bot_id, executed_slices
                    )
                    executed_slices += 1
                    continue

                try:
                    order = await adapter.place_order(
                        OrderRequest(
                            symbol=symbol,
                            side=config.side,
                            order_type=config.order_type,
                            qty=qty,
                        )
                    )
                    executed_slices += 1
                    r.set(
                        state_key,
                        json.dumps(
                            {
                                "executed_slices": executed_slices,
                                "initial_price": str(initial_price) if initial_price else None,
                            }
                        ),
                    )
                    logger.info(
                        "TWAP slice executed: bot_id=%s %d/%d qty=%s order_id=%s",
                        bot_id, executed_slices, config.num_slices, qty, order.exchange_order_id,
                    )
                    _create_bot_log(
                        bot_id=bot_id,
                        event_type="algo_slice_executed",
                        level="info",
                        message="TWAP slice order executed",
                        payload={
                            "executed_slices": executed_slices,
                            "num_slices": config.num_slices,
                            "qty": str(qty),
                            "order_id": order.exchange_order_id,
                        },
                    )
                except Exception as exc:
                    logger.error(
                        "Slice order error: bot_id=%s slice=%d error=%s",
                        bot_id, executed_slices, exc,
                    )
                    _create_bot_log(
                        bot_id=bot_id,
                        event_type="order_error",
                        level="error",
                        message=f"Slice order error: {exc}",
                        payload={"executed_slices": executed_slices},
                    )

                if not is_completed(executed_slices, config.num_slices) and interval_sec > 0:
                    await asyncio.sleep(interval_sec)

        finally:
            await adapter.close()
            r.delete(state_key)

        if final_status == "completed":
            _update_bot_status_completed(bot_id=bot_id, reason=final_reason)
        else:
            _update_bot_status_stopped(bot_id=bot_id, reason=final_reason)
        logger.info(
            "Algo Orders bot stopped: bot_id=%s executed=%d/%d",
            bot_id, executed_slices, config.num_slices,
        )

    self.run_async(_run())
