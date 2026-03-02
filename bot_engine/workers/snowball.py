"""Position Snowball 봇 Celery Worker.

전략:
  - 가격이 하락할 때마다 분할 매수 (물타기)
  - 각 분할 매수마다 평균 매입가 낮춤
  - 목표 수익률 도달 시 전체 포지션 청산
  - 최대 분할 횟수 제한으로 리스크 관리

Redis 정지 신호: redis.set(f"bot:{bot_id}:stop", "1")
"""
from __future__ import annotations

import logging

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
    name="bot_engine.workers.snowball.run",
    max_retries=0,
    acks_late=True,
)
def run_snowball(self, *, bot_id: str) -> None:
    """Position Snowball 봇 실행 Task."""

    async def _run() -> None:
        from app.core.config import settings
        from bot_engine.utils.crypto import decrypt
        from bot_engine.exchange_adapters import get_adapter

        from sqlmodel import Session, select, create_engine
        from app.models import Bot, ExchangeAccount

        engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
        with Session(engine) as session:
            bot = session.exec(select(Bot).where(Bot.id == __import__("uuid").UUID(bot_id))).first()
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
            extra_params = None
            if account.extra_params_enc:
                import json
                extra_params = json.loads(decrypt(account.extra_params_enc, settings.ENCRYPTION_KEY))

        adapter = get_adapter(
            exchange=account.exchange,
            api_key=api_key,
            api_secret=api_secret,
            extra_params=extra_params,
        )

        _update_bot_status_running(bot_id=bot_id, celery_task_id=self.request.id)
        logger.info("Snowball bot started: bot_id=%s symbol=%s", bot_id, bot.symbol)

        try:
            # TODO: bot.config에서 설정 로드
            # config = bot.config  # {"drop_pct": "5", "qty_per_buy": "0.01", "take_profit_pct": "3", "max_buys": 5}
            # 초기 매수 주문 배치
            # ...

            async for tick in adapter.price_stream(bot.symbol or "BTC/USDT"):
                if should_stop(bot_id):
                    logger.info("Stop signal received: bot_id=%s", bot_id)
                    clear_stop_signal(bot_id)
                    break

                # TODO: 분할 매수 / 익절 청산 로직
                # current_price = tick.price
                # check_drop_and_buy(current_price, ...)
                # check_take_profit(current_price, ...)
                logger.debug("Price tick: %s @ %s", tick.symbol, tick.price)

        finally:
            await adapter.close()

        _update_bot_status_stopped(bot_id=bot_id)
        logger.info("Snowball bot stopped: bot_id=%s", bot_id)

    self.run_async(_run())
