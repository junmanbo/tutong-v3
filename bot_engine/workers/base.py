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

import redis
from celery import Task

from bot_engine.celery_app import celery_app

logger = logging.getLogger(__name__)
UTC = timezone.utc


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
        _update_bot_status_error(bot_id=bot_id, error_message=str(exc))

    def on_success(self, retval, task_id, args, kwargs) -> None:
        bot_id = kwargs.get("bot_id", "unknown")
        logger.info("Bot task completed: bot_id=%s task_id=%s", bot_id, task_id)


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
    """Bot Engine에서 DB 세션 반환."""
    import os
    from sqlmodel import Session, create_engine

    db_url = os.environ.get(
        "SQLALCHEMY_DATABASE_URI",
        "postgresql+psycopg://postgres:changethis@localhost:5432/app",
    )
    engine = create_engine(db_url)
    return Session(engine)


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
    except Exception as e:
        logger.error("Failed to update bot status to running: %s", e)


def _update_bot_status_stopped(bot_id: str) -> None:
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
                session.add(bot)
                session.commit()
    except Exception as e:
        logger.error("Failed to update bot status to stopped: %s", e)
