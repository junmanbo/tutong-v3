"""Spot Grid 봇 Celery Worker.

전략:
  - 상한가(upper)와 하한가(lower) 사이를 grid_count 개의 구간으로 분할
  - 각 그리드 레벨에 지정가 매수/매도 주문을 배치
  - 가격이 하락하여 매수 체결 → 상위 그리드에 매도 주문 배치
  - 가격이 상승하여 매도 체결 → 하위 그리드에 매수 주문 배치

Redis 정지 신호: redis.set(f"bot:{bot_id}:stop", "1")
"""
from __future__ import annotations

import logging
import os

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
    name="bot_engine.workers.spot_grid.run",
    max_retries=0,       # 봇 오류는 수동 재시작
    acks_late=True,
)
def run_spot_grid(self, *, bot_id: str) -> None:
    """Spot Grid 봇 실행 Task."""

    async def _run() -> None:
        from decimal import Decimal

        from app.core.config import settings
        from app.core.crypto import encrypt  # noqa: F401
        from bot_engine.utils.crypto import decrypt
        from bot_engine.utils.decimal_utils import apply_lot_size, calculate_grid_prices
        from bot_engine.exchange_adapters import get_adapter

        import asyncio
        from sqlmodel import Session, select, create_engine
        from app.models import Bot, ExchangeAccount

        # DB에서 봇/계좌 정보 로드
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

            # API Key 복호화
            api_key = decrypt(account.api_key_enc, settings.ENCRYPTION_KEY)
            api_secret = decrypt(account.api_secret_enc, settings.ENCRYPTION_KEY)
            extra_params = None
            if account.extra_params_enc:
                import json
                extra_params = json.loads(decrypt(account.extra_params_enc, settings.ENCRYPTION_KEY))

        # 어댑터 생성
        adapter = get_adapter(
            exchange=account.exchange,
            api_key=api_key,
            api_secret=api_secret,
            extra_params=extra_params,
        )

        # 봇 상태 → running 업데이트
        _update_bot_status_running(bot_id=bot_id, celery_task_id=self.request.id)
        logger.info("Spot Grid bot started: bot_id=%s symbol=%s", bot_id, bot.symbol)

        try:
            # TODO: 봇 설정(bot_config_grid) 로드 후 그리드 초기화
            # grid_prices = calculate_grid_prices(upper, lower, grid_count)
            # 초기 그리드 주문 배치
            # ...

            # 메인 루프: 가격 스트림 수신 + 체결 처리
            async for tick in adapter.price_stream(bot.symbol or "BTC/USDT"):
                if should_stop(bot_id):
                    logger.info("Stop signal received: bot_id=%s", bot_id)
                    clear_stop_signal(bot_id)
                    break

                # TODO: 그리드 체결 확인 및 신규 주문 배치 로직
                # current_price = tick.price
                # check_grid_fills(current_price, grid_orders)
                # place_new_orders(...)
                logger.debug("Price tick: %s @ %s", tick.symbol, tick.price)

        finally:
            await adapter.close()

        _update_bot_status_stopped(bot_id=bot_id)
        logger.info("Spot Grid bot stopped: bot_id=%s", bot_id)

    self.run_async(_run())
