"""봇 Worker 베이스 클래스.

모든 봇 Celery Task는 AsyncBotTask를 상속합니다.
Celery는 동기 환경이므로 asyncio 코루틴을 전용 이벤트 루프에서 실행합니다.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import redis
from celery import Task

from bot_engine.celery_app import celery_app

logger = logging.getLogger(__name__)
UTC = timezone.utc

# ── DB 엔진 싱글턴 ─────────────────────────────────────────────────────────────
_db_engine = None


def _get_engine():
    """모듈 레벨 싱글턴 SQLAlchemy 엔진 반환."""
    global _db_engine
    if _db_engine is None:
        from sqlmodel import create_engine
        db_url = os.environ.get("SQLALCHEMY_DATABASE_URI")
        if not db_url:
            from app.core.config import settings

            db_url = str(settings.SQLALCHEMY_DATABASE_URI)
        _db_engine = create_engine(db_url, pool_pre_ping=True)
    return _db_engine


class AsyncBotTask(Task):
    """asyncio 코루틴을 Celery Task에서 안전하게 실행하는 베이스 클래스.

    사용 패턴:
        @celery_app.task(bind=True, base=AsyncBotTask, max_retries=0)
        def run_my_bot(self, *, bot_id: str) -> None:
            async def _run():
                ...
            self.run_async(_run())
    """

    abstract = True
    _loop: asyncio.AbstractEventLoop | None = None

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def run_async(self, coro) -> object:
        """새 이벤트 루프에서 코루틴 실행."""
        return self.loop.run_until_complete(coro)

    def on_failure(self, exc, task_id, args, kwargs, einfo) -> None:
        bot_id = kwargs.get("bot_id", "unknown")
        logger.error(
            "Bot task failed: bot_id=%s task_id=%s error=%s",
            bot_id,
            task_id,
            exc,
            exc_info=einfo,
        )
        if bot_id != "unknown":
            _create_bot_log(
                bot_id=bot_id,
                event_type="task_failure",
                level="error",
                message=f"Bot task failed: {exc}",
                payload={"task_id": task_id},
            )
        _update_bot_status_error(bot_id=bot_id, error_message=str(exc))

    def on_success(self, retval, task_id, args, kwargs) -> None:
        bot_id = kwargs.get("bot_id", "unknown")
        logger.info("Bot task completed: bot_id=%s task_id=%s", bot_id, task_id)
        if bot_id != "unknown":
            _create_bot_log(
                bot_id=bot_id,
                event_type="task_success",
                level="info",
                message="Bot task completed successfully",
                payload={"task_id": task_id},
            )


# ── Redis 정지 신호 ────────────────────────────────────────────────────────────


def get_redis() -> redis.Redis:
    """Redis 클라이언트 반환 (동기)."""
    return redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )


def should_stop(bot_id: str) -> bool:
    """Redis에서 봇 정지 신호 확인."""
    r = get_redis()
    return bool(r.get(f"bot:{bot_id}:stop"))


def clear_stop_signal(bot_id: str) -> None:
    """Redis 봇 정지 신호 삭제."""
    r = get_redis()
    r.delete(f"bot:{bot_id}:stop")


# ── DB 상태 업데이트 헬퍼 ─────────────────────────────────────────────────────


def _get_db_session():
    """Bot Engine에서 DB 세션 반환 (싱글턴 엔진 재사용)."""
    from sqlmodel import Session
    return Session(_get_engine())


def _update_bot_status_error(bot_id: str, error_message: str) -> None:
    """봇 상태를 error로 업데이트."""
    try:
        from sqlmodel import select
        from app.models import Bot, BotStatusEnum

        with _get_db_session() as session:
            bot = session.exec(
                select(Bot).where(Bot.id == uuid.UUID(bot_id))
            ).first()
            if bot:
                bot.status = BotStatusEnum.error
                bot.error_message = error_message
                bot.updated_at = datetime.now(UTC)
                session.add(bot)
                session.commit()
                _create_bot_log(
                    bot_id=bot.id,
                    event_type="bot_error",
                    level="error",
                    message=error_message,
                )
                try:
                    from app.notifications import (
                        EVENT_BOT_ERROR,
                        queue_notification_event,
                    )

                    queue_notification_event(
                        session=session,
                        user_id=bot.user_id,
                        bot_id=bot.id,
                        event_type=EVENT_BOT_ERROR,
                        title=f"[AutoTrade] Bot error: {bot.name}",
                        body=error_message,
                        payload={"status": bot.status.value},
                    )
                except Exception as notify_exc:
                    logger.warning("Failed to queue bot error notification: %s", notify_exc)
    except Exception as e:
        logger.error("Failed to update bot status to error: %s", e)


def _update_bot_status_running(bot_id: str, celery_task_id: str) -> None:
    """봇 상태를 running으로 업데이트."""
    try:
        from sqlmodel import select
        from app.models import Bot, BotStatusEnum

        with _get_db_session() as session:
            bot = session.exec(
                select(Bot).where(Bot.id == uuid.UUID(bot_id))
            ).first()
            if bot:
                bot.status = BotStatusEnum.running
                bot.celery_task_id = celery_task_id
                bot.started_at = datetime.now(UTC)
                bot.updated_at = datetime.now(UTC)
                session.add(bot)
                session.commit()
                _create_bot_log(
                    bot_id=bot.id,
                    event_type="bot_running",
                    level="info",
                    message="Bot is now running",
                    payload={"celery_task_id": celery_task_id},
                )
    except Exception as e:
        logger.error("Failed to update bot status to running: %s", e)


def _update_bot_status_stopped(bot_id: str, reason: str | None = None) -> None:
    """봇 상태를 stopped로 업데이트."""
    try:
        from sqlmodel import select
        from app.models import Bot, BotStatusEnum

        with _get_db_session() as session:
            bot = session.exec(
                select(Bot).where(Bot.id == uuid.UUID(bot_id))
            ).first()
            if bot:
                bot.status = BotStatusEnum.stopped
                bot.celery_task_id = None
                bot.stopped_at = datetime.now(UTC)
                bot.updated_at = datetime.now(UTC)
                if reason:
                    bot.error_message = reason
                session.add(bot)
                session.commit()
                _create_bot_log(
                    bot_id=bot.id,
                    event_type="bot_stopped",
                    level="warning" if reason else "info",
                    message=reason or "Bot stopped",
                )
                if reason and "stop-loss" in reason.lower():
                    try:
                        from app.notifications import (
                            EVENT_STOP_LOSS,
                            queue_notification_event,
                        )

                        queue_notification_event(
                            session=session,
                            user_id=bot.user_id,
                            bot_id=bot.id,
                            event_type=EVENT_STOP_LOSS,
                            title=f"[AutoTrade] Stop-loss triggered: {bot.name}",
                            body=reason,
                            payload={"status": bot.status.value},
                        )
                    except Exception as notify_exc:
                        logger.warning(
                            "Failed to queue stop-loss notification: %s", notify_exc
                        )
    except Exception as e:
        logger.error("Failed to update bot status to stopped: %s", e)


def _update_bot_status_completed(bot_id: str, reason: str | None = None) -> None:
    """봇 상태를 completed로 업데이트."""
    try:
        from sqlmodel import select
        from app.models import Bot, BotStatusEnum

        with _get_db_session() as session:
            bot = session.exec(
                select(Bot).where(Bot.id == uuid.UUID(bot_id))
            ).first()
            if bot:
                bot.status = BotStatusEnum.completed
                bot.celery_task_id = None
                bot.stopped_at = datetime.now(UTC)
                bot.updated_at = datetime.now(UTC)
                if reason:
                    bot.error_message = reason
                session.add(bot)
                session.commit()
                _create_bot_log(
                    bot_id=bot.id,
                    event_type="bot_completed",
                    level="info",
                    message=reason or "Bot completed",
                )
                if reason and "take-profit" in reason.lower():
                    try:
                        from app.notifications import (
                            EVENT_TAKE_PROFIT,
                            queue_notification_event,
                        )

                        queue_notification_event(
                            session=session,
                            user_id=bot.user_id,
                            bot_id=bot.id,
                            event_type=EVENT_TAKE_PROFIT,
                            title=f"[AutoTrade] Take-profit reached: {bot.name}",
                            body=reason,
                            payload={"status": bot.status.value},
                        )
                    except Exception as notify_exc:
                        logger.warning(
                            "Failed to queue take-profit notification: %s", notify_exc
                        )
    except Exception as e:
        logger.error("Failed to update bot status to completed: %s", e)


def _update_bot_total_pnl_pct(bot_id: str, pnl_pct: Decimal) -> None:
    """봇 total_pnl_pct를 최신 값으로 업데이트."""
    try:
        from sqlmodel import select
        from app.models import Bot

        with _get_db_session() as session:
            bot = session.exec(
                select(Bot).where(Bot.id == uuid.UUID(bot_id))
            ).first()
            if bot:
                bot.total_pnl_pct = pnl_pct
                bot.updated_at = datetime.now(UTC)
                session.add(bot)
                session.commit()
    except Exception as e:
        logger.error("Failed to update bot total_pnl_pct: %s", e)


def _create_bot_log(
    *,
    bot_id: uuid.UUID | str,
    event_type: str,
    level: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """봇 실행 로그를 DB에 저장."""
    try:
        from app.models import BotLog

        resolved_bot_id = (
            bot_id if isinstance(bot_id, uuid.UUID) else uuid.UUID(str(bot_id))
        )
        with _get_db_session() as session:
            session.add(
                BotLog(
                    bot_id=resolved_bot_id,
                    event_type=event_type,
                    level=level,
                    message=message,
                    payload=payload or {},
                )
            )
            session.commit()
    except Exception as e:
        logger.error("Failed to create bot log: %s", e)


def _normalize_order_status(status: str | None) -> str:
    if not status:
        return "open"
    normalized = status.lower()
    mapping = {
        "closed": "filled",
        "cancelled": "canceled",
    }
    return mapping.get(normalized, normalized)


def _to_decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _record_order_and_trade(
    *,
    bot_id: uuid.UUID | str,
    order: Any,
    qty_hint: Decimal | None = None,
    price_hint: Decimal | None = None,
) -> None:
    """주문/체결 데이터를 bot_orders, bot_trades에 저장(또는 갱신).

    - 동일 exchange_order_id가 존재하면 bot_orders를 upsert 업데이트
    - filled_qty > 0 이면 bot_trades를 1건 생성(동일 order_id 중복 방지)
    """
    try:
        from sqlmodel import select

        from app.models import BotOrder, BotTrade

        resolved_bot_id = (
            bot_id if isinstance(bot_id, uuid.UUID) else uuid.UUID(str(bot_id))
        )
        now = datetime.now(UTC)

        requested_qty = order.requested_qty or qty_hint or order.filled_qty or Decimal("0")
        filled_qty = order.filled_qty or Decimal("0")
        raw_price = _to_decimal_or_none((order.raw or {}).get("price"))
        order_price = raw_price or price_hint
        avg_fill_price = order.avg_fill_price or order_price
        normalized_status = _normalize_order_status(order.status)
        filled_at = (
            now
            if filled_qty > Decimal("0")
            and normalized_status in {"filled", "partially_filled"}
            else None
        )

        with _get_db_session() as session:
            db_order = session.exec(
                select(BotOrder).where(
                    BotOrder.bot_id == resolved_bot_id,
                    BotOrder.exchange_order_id == order.exchange_order_id,
                )
            ).first()

            if db_order is None:
                db_order = BotOrder(
                    bot_id=resolved_bot_id,
                    exchange_order_id=order.exchange_order_id,
                    symbol=order.symbol,
                    side=order.side,
                    order_type=order.order_type,
                    status=normalized_status,
                    quantity=requested_qty,
                    price=order_price,
                    avg_fill_price=avg_fill_price,
                    filled_quantity=filled_qty,
                    fee=order.fee or Decimal("0"),
                    fee_currency=order.fee_currency or None,
                    placed_at=now,
                    filled_at=filled_at,
                )
                session.add(db_order)
                session.commit()
                session.refresh(db_order)
            else:
                db_order.symbol = order.symbol or db_order.symbol
                db_order.side = order.side or db_order.side
                db_order.order_type = order.order_type or db_order.order_type
                db_order.status = normalized_status
                db_order.quantity = requested_qty
                db_order.price = order_price
                db_order.avg_fill_price = avg_fill_price
                db_order.filled_quantity = filled_qty
                db_order.fee = order.fee or Decimal("0")
                db_order.fee_currency = order.fee_currency or db_order.fee_currency
                if filled_at is not None:
                    db_order.filled_at = filled_at
                db_order.updated_at = now
                session.add(db_order)
                session.commit()
                session.refresh(db_order)

            # 동일 주문(order_id)에 대한 trade는 1건만 저장 (중복 방지)
            if filled_qty > Decimal("0"):
                existing_trade = session.exec(
                    select(BotTrade).where(BotTrade.order_id == db_order.id)
                ).first()
                if existing_trade is None:
                    trade_price = avg_fill_price or price_hint or Decimal("0")
                    if trade_price > Decimal("0"):
                        trade_id = None
                        raw_trades = (order.raw or {}).get("trades")
                        if (
                            isinstance(raw_trades, list)
                            and raw_trades
                            and isinstance(raw_trades[0], dict)
                        ):
                            trade_id = raw_trades[0].get("id")
                        session.add(
                            BotTrade(
                                order_id=db_order.id,
                                bot_id=resolved_bot_id,
                                exchange_trade_id=(
                                    str(trade_id)
                                    if trade_id
                                    else f"{order.exchange_order_id}:fill"
                                ),
                                quantity=filled_qty,
                                price=trade_price,
                                fee=order.fee or Decimal("0"),
                                fee_currency=order.fee_currency or db_order.fee_currency,
                                traded_at=filled_at or now,
                            )
                        )
                        session.commit()
    except Exception as e:
        logger.error("Failed to record order/trade: %s", e)


async def _resolve_order_fill(
    *,
    adapter: Any,
    order: Any,
    symbol: str,
    retries: int = 2,
    delay_seconds: float = 1.0,
) -> Any:
    """주문 직후 체결 정보가 비어있는 경우 짧게 재조회하여 보정."""
    resolved = order
    try:
        status = _normalize_order_status(getattr(resolved, "status", None))
        filled_qty = getattr(resolved, "filled_qty", Decimal("0")) or Decimal("0")
        if filled_qty > Decimal("0") or status in {"filled", "partially_filled"}:
            return resolved

        for _ in range(retries):
            await asyncio.sleep(delay_seconds)
            latest = await adapter.get_order(order.exchange_order_id, symbol)
            if latest is None:
                continue
            resolved = latest
            status = _normalize_order_status(getattr(resolved, "status", None))
            filled_qty = getattr(resolved, "filled_qty", Decimal("0")) or Decimal("0")
            if filled_qty > Decimal("0") or status in {"filled", "partially_filled"}:
                break
    except Exception as exc:
        logger.warning("Failed to resolve order fill: %s", exc)
    return resolved


def calc_change_pct(current_value: Decimal, base_value: Decimal) -> Decimal:
    """기준값 대비 변동률(%) 계산."""
    if base_value <= Decimal("0"):
        return Decimal("0")
    return (current_value - base_value) / base_value * Decimal("100")


def evaluate_risk_limits(
    *,
    change_pct: Decimal,
    stop_loss_pct: Decimal | None,
    take_profit_pct: Decimal | None,
) -> tuple[str, str] | None:
    """손절/익절 임계값 체크.

    Returns:
        ("stopped", reason) | ("completed", reason) | None
    """
    if stop_loss_pct is not None and change_pct <= -abs(stop_loss_pct):
        return (
            "stopped",
            f"Auto stop-loss triggered at {change_pct:.4f}% (limit {stop_loss_pct}%)",
        )
    if take_profit_pct is not None and change_pct >= take_profit_pct:
        return (
            "completed",
            f"Auto take-profit triggered at {change_pct:.4f}% (target {take_profit_pct}%)",
        )
    return None
