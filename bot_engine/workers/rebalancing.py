"""Rebalancing 봇 Celery Worker.

전략:
  - 다자산 포트폴리오의 목표 비중 설정
  - 주기적(또는 임계값 초과 시) 현재 비중과 목표 비중 비교
  - 비중 차이가 임계값(threshold_pct) 초과 시 리밸런싱 주문 실행
  - 과매수 자산 매도 → 과매도 자산 매수

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
    name="bot_engine.workers.rebalancing.run",
    max_retries=0,
    acks_late=True,
)
def run_rebalancing(self, *, bot_id: str) -> None:
    """Rebalancing 봇 실행 Task."""

    async def _run() -> None:
        import asyncio
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
        logger.info("Rebalancing bot started: bot_id=%s", bot_id)

        try:
            # TODO: bot.config에서 설정 로드
            # config = bot.config
            # {
            #   "assets": {"BTC": "50", "ETH": "30", "USDT": "20"},  # 목표 비중(%)
            #   "threshold_pct": "5",   # 리밸런싱 임계값
            #   "interval_seconds": 3600,  # 주기 체크 간격
            # }
            # interval_seconds = int(config.get("interval_seconds", 3600))

            while True:
                if should_stop(bot_id):
                    logger.info("Stop signal received: bot_id=%s", bot_id)
                    clear_stop_signal(bot_id)
                    break

                # TODO: 잔고 조회 → 비중 계산 → 임계값 초과 시 리밸런싱 주문
                # balances = await adapter.get_balance()
                # rebalance_if_needed(balances, target_weights, threshold_pct)
                logger.debug("Rebalancing check: bot_id=%s", bot_id)

                await asyncio.sleep(3600)  # TODO: config에서 interval 읽기

        finally:
            await adapter.close()

        _update_bot_status_stopped(bot_id=bot_id)
        logger.info("Rebalancing bot stopped: bot_id=%s", bot_id)

    self.run_async(_run())
