"""Position Snowball 봇 Celery Worker.

전략:
  - 가격이 하락할 때마다 분할 매수 (물타기)
  - 각 분할 매수마다 평균 매입가 낮춤
  - 목표 수익률 도달 시 전체 포지션 청산
  - 최대 분할 횟수 제한으로 리스크 관리

Redis 정지 신호: redis.set(f"bot:{bot_id}:stop", "1")
"""
from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal

from bot_engine.celery_app import celery_app
from bot_engine.workers.base import (
    AsyncBotTask,
    _create_bot_log,
    _get_db_session,
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
    name="bot_engine.workers.snowball.run",
    max_retries=0,
    acks_late=True,
)
def run_snowball(self, *, bot_id: str) -> None:
    """Position Snowball 봇 실행 Task."""

    async def _run() -> None:
        from sqlmodel import select

        from app.core.config import settings
        from app.exchange_adapters.base import OrderRequest
        from app.models import Bot, ExchangeAccount
        from bot_engine.exchange_adapters import get_adapter
        from bot_engine.strategies.snowball import (
            BuyRecord,
            SnowballConfig,
            calc_avg_price,
            calc_buy_qty,
            calc_total_qty,
            should_add_buy,
            should_take_profit,
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
        config = SnowballConfig.from_dict(symbol, bot_config)

        adapter = get_adapter(
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret,
            extra_params=extra_params,
        )

        _update_bot_status_running(bot_id=bot_id, celery_task_id=self.request.id)
        logger.info(
            "Snowball bot started: bot_id=%s symbol=%s drop_pct=%s tp_pct=%s max_buys=%d",
            bot_id, symbol, config.drop_pct, config.take_profit_pct, config.max_buys,
        )
        _create_bot_log(
            bot_id=bot_id,
            event_type="snowball_started",
            level="info",
            message="Snowball bot started",
            payload={"symbol": symbol, "max_buys": config.max_buys},
        )

        # ── Redis에서 이전 상태 복원 ─────────────────────────────────────────
        r = get_redis()
        state_key = f"bot:{bot_id}:snowball_state"
        state_raw = r.get(state_key)
        buys: list[BuyRecord] = []
        if state_raw:
            raw_buys: list[dict] = json.loads(state_raw)
            buys = [BuyRecord(price=Decimal(b["price"]), qty=Decimal(b["qty"])) for b in raw_buys]

        def save_state() -> None:
            r.set(state_key, json.dumps([
                {"price": str(b.price), "qty": str(b.qty)} for b in buys
            ]))

        final_status = "stopped"
        final_reason: str | None = None

        try:
            # 포지션이 없으면 초기 매수
            if not buys:
                ticker = await adapter.get_ticker(symbol)
                price = ticker.price
                qty = calc_buy_qty(config.amount_per_buy, price, config.step_size)
                if qty > Decimal("0"):
                    order = await adapter.place_order(
                        OrderRequest(
                            symbol=symbol, side="buy",
                            order_type="market", qty=qty,
                        )
                    )
                    buys.append(BuyRecord(price=price, qty=qty))
                    save_state()
                    logger.info(
                        "Snowball initial buy: price=%s qty=%s order_id=%s",
                        price, qty, order.exchange_order_id,
                    )
                    _create_bot_log(
                        bot_id=bot_id,
                        event_type="order_placed",
                        level="info",
                        message="Snowball initial buy order placed",
                        payload={
                            "order_id": order.exchange_order_id,
                            "price": str(price),
                            "qty": str(qty),
                        },
                    )

            # ── 메인 루프: 가격 스트림 ───────────────────────────────────────
            async for tick in adapter.price_stream(symbol):
                if should_stop(bot_id):
                    logger.info("Stop signal received: bot_id=%s", bot_id)
                    clear_stop_signal(bot_id)
                    break

                current_price = tick.price
                avg_price = calc_avg_price(buys)
                total_qty = calc_total_qty(buys)
                if total_qty > Decimal("0") and avg_price > Decimal("0"):
                    pnl_pct = calc_change_pct(current_price, avg_price)
                    _update_bot_total_pnl_pct(bot_id=bot_id, pnl_pct=pnl_pct)
                    risk = evaluate_risk_limits(
                        change_pct=pnl_pct,
                        stop_loss_pct=stop_loss_pct,
                        take_profit_pct=take_profit_pct,
                    )
                    if risk:
                        status, reason = risk
                        try:
                            order = await adapter.place_order(
                                OrderRequest(
                                    symbol=symbol,
                                    side="sell",
                                    order_type="market",
                                    qty=total_qty,
                                )
                            )
                            logger.info(
                                "Snowball risk exit: status=%s price=%s avg=%s qty=%s order_id=%s",
                                status,
                                current_price,
                                avg_price,
                                total_qty,
                                order.exchange_order_id,
                            )
                            _create_bot_log(
                                bot_id=bot_id,
                                event_type="risk_exit_order",
                                level="warning",
                                message="Snowball risk-exit sell order placed",
                                payload={
                                    "status": status,
                                    "order_id": order.exchange_order_id,
                                    "qty": str(total_qty),
                                },
                            )
                            buys.clear()
                            save_state()
                            final_status = status
                            final_reason = reason
                            break
                        except Exception as exc:
                            logger.error("Risk exit order error: %s", exc)
                            _create_bot_log(
                                bot_id=bot_id,
                                event_type="order_error",
                                level="error",
                                message=f"Risk exit order error: {exc}",
                            )

                # 익절 조건 확인
                if total_qty > Decimal("0") and should_take_profit(
                    current_price, avg_price, config.take_profit_pct
                ):
                    try:
                        order = await adapter.place_order(
                            OrderRequest(
                                symbol=symbol, side="sell",
                                order_type="market", qty=total_qty,
                            )
                        )
                        logger.info(
                            "Snowball take profit: price=%s avg=%s qty=%s order_id=%s",
                            current_price, avg_price, total_qty, order.exchange_order_id,
                        )
                        _create_bot_log(
                            bot_id=bot_id,
                            event_type="take_profit_order",
                            level="info",
                            message="Snowball take-profit sell order placed",
                            payload={
                                "order_id": order.exchange_order_id,
                                "qty": str(total_qty),
                                "price": str(current_price),
                            },
                        )
                        buys.clear()
                        save_state()
                        final_status = "completed"
                        final_reason = "Snowball strategy take-profit completed"
                        break  # 익절 후 봇 완료
                    except Exception as exc:
                        logger.error("Take profit order error: %s", exc)
                        _create_bot_log(
                            bot_id=bot_id,
                            event_type="order_error",
                            level="error",
                            message=f"Take-profit order error: {exc}",
                        )

                # 추가 매수 조건 확인
                elif len(buys) < config.max_buys and should_add_buy(
                    current_price, buys[-1].price if buys else Decimal("0"), config.drop_pct
                ):
                    try:
                        qty = calc_buy_qty(config.amount_per_buy, current_price, config.step_size)
                        if qty > Decimal("0"):
                            order = await adapter.place_order(
                                OrderRequest(
                                    symbol=symbol, side="buy",
                                    order_type="market", qty=qty,
                                )
                            )
                            buys.append(BuyRecord(price=current_price, qty=qty))
                            save_state()
                            logger.info(
                                "Snowball add buy #%d: price=%s qty=%s order_id=%s",
                                len(buys), current_price, qty, order.exchange_order_id,
                            )
                            _create_bot_log(
                                bot_id=bot_id,
                                event_type="add_buy_order",
                                level="info",
                                message="Snowball additional buy order placed",
                                payload={
                                    "buy_count": len(buys),
                                    "order_id": order.exchange_order_id,
                                    "qty": str(qty),
                                    "price": str(current_price),
                                },
                            )
                    except Exception as exc:
                        logger.error("Add buy order error: %s", exc)
                        _create_bot_log(
                            bot_id=bot_id,
                            event_type="order_error",
                            level="error",
                            message=f"Add buy order error: {exc}",
                        )

        finally:
            await adapter.close()
            r.delete(state_key)

        if final_status == "completed":
            _update_bot_status_completed(bot_id=bot_id, reason=final_reason)
        else:
            _update_bot_status_stopped(bot_id=bot_id, reason=final_reason)
        logger.info("Snowball bot stopped: bot_id=%s buys=%d", bot_id, len(buys))

    self.run_async(_run())
