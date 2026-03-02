"""Algo Orders (TWAP) 봇 Celery Worker.

전략:
  - TWAP(Time-Weighted Average Price): 대량 주문을 시간 가중 평균가로 분할 실행
  - 지정된 시간 동안 균등 분할 주문으로 시장 충격 최소화
  - 각 슬라이스는 total_qty / num_slices 수량으로 실행

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
    name="bot_engine.workers.algo_orders.run",
    max_retries=0,
    acks_late=True,
)
def run_algo_orders(self, *, bot_id: str) -> None:
    """Algo Orders (TWAP) 봇 실행 Task."""

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
        logger.info("Algo Orders bot started: bot_id=%s symbol=%s", bot_id, bot.symbol)

        try:
            # TODO: bot.config에서 설정 로드
            # config = bot.config
            # {
            #   "side": "buy",            # "buy" | "sell"
            #   "total_qty": "1.0",       # 총 주문 수량
            #   "num_slices": 10,         # 분할 횟수
            #   "duration_seconds": 3600, # 총 실행 시간 (초)
            #   "order_type": "market",   # "market" | "limit"
            # }
            # num_slices = int(config.get("num_slices", 10))
            # duration = int(config.get("duration_seconds", 3600))
            # interval = duration / num_slices

            executed_slices = 0
            while True:
                if should_stop(bot_id):
                    logger.info("Stop signal received: bot_id=%s", bot_id)
                    clear_stop_signal(bot_id)
                    break

                # TODO: TWAP 슬라이스 주문 실행
                # slice_qty = total_qty / num_slices (apply_lot_size 적용)
                # order = await adapter.place_order(OrderRequest(..., quantity=slice_qty))
                # executed_slices += 1
                # if executed_slices >= num_slices: break (완료)
                logger.debug("TWAP slice: bot_id=%s executed=%d", bot_id, executed_slices)

                await asyncio.sleep(360)  # TODO: config에서 interval 계산

        finally:
            await adapter.close()

        _update_bot_status_stopped(bot_id=bot_id)
        logger.info("Algo Orders bot stopped: bot_id=%s", bot_id)

    self.run_async(_run())
