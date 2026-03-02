"""Spot DCA (Dollar-Cost Averaging) 봇 Celery Worker.

전략:
  - 정해진 주기(interval)마다 정액(amount) 또는 정량(qty) 자동 매수
  - 시장가 또는 지정가(VWAP 기준) 주문
  - 장기 적립식 매수로 평균 매입가 분산

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
    name="bot_engine.workers.spot_dca.run",
    max_retries=0,
    acks_late=True,
)
def run_spot_dca(self, *, bot_id: str) -> None:
    """Spot DCA 봇 실행 Task."""

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
        logger.info("Spot DCA bot started: bot_id=%s symbol=%s", bot_id, bot.symbol)

        try:
            # TODO: bot.config에서 설정 로드
            # config = bot.config
            # {
            #   "amount_per_order": "100",   # 매수 금액 (USDT)
            #   "interval_seconds": 86400,   # 매수 주기 (초), 기본 1일
            #   "order_type": "market",      # "market" | "limit"
            #   "total_orders": 30,          # 총 매수 횟수 (옵션, 없으면 무한)
            # }
            # interval_seconds = int(config.get("interval_seconds", 86400))

            order_count = 0
            while True:
                if should_stop(bot_id):
                    logger.info("Stop signal received: bot_id=%s", bot_id)
                    clear_stop_signal(bot_id)
                    break

                # TODO: 정기 매수 주문 실행
                # order = await adapter.place_order(OrderRequest(symbol=bot.symbol, side="buy", ...))
                # order_count += 1
                # if total_orders and order_count >= total_orders: break
                logger.debug("DCA order check: bot_id=%s count=%d", bot_id, order_count)

                await asyncio.sleep(86400)  # TODO: config에서 interval 읽기

        finally:
            await adapter.close()

        _update_bot_status_stopped(bot_id=bot_id)
        logger.info("Spot DCA bot stopped: bot_id=%s", bot_id)

    self.run_async(_run())
