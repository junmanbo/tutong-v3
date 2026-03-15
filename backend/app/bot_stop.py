from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.config import settings
from app.core.crypto import decrypt
from app.exchange_adapters.base import AbstractExchangeAdapter
from app.exchange_adapters.factory import get_adapter
from app.models import Bot, BotOrder, ExchangeAccount

UTC = timezone.utc
OPEN_ORDER_STATUSES = ("open", "pending", "partially_filled")


@dataclass
class CancelOpenOrdersResult:
    attempted: int = 0
    canceled: int = 0
    failed: int = 0


async def cancel_open_orders_with_adapter(
    *,
    session: Session,
    bot_id: uuid.UUID,
    adapter: AbstractExchangeAdapter,
) -> CancelOpenOrdersResult:
    open_orders = list(
        session.exec(
            select(BotOrder).where(
                BotOrder.bot_id == bot_id,
                BotOrder.status.in_(OPEN_ORDER_STATUSES),
            )
        ).all()
    )
    result = CancelOpenOrdersResult(attempted=len(open_orders))
    if not open_orders:
        return result

    now = datetime.now(UTC)
    for order in open_orders:
        try:
            await adapter.cancel_order(order.exchange_order_id, order.symbol)
        except Exception:
            result.failed += 1
            continue

        order.status = "canceled"
        order.updated_at = now
        session.add(order)
        result.canceled += 1

    session.commit()
    return result


def cancel_open_orders_for_bot(
    *,
    session: Session,
    bot: Bot,
    account: ExchangeAccount,
) -> CancelOpenOrdersResult:
    has_open_orders = session.exec(
        select(BotOrder.id).where(
            BotOrder.bot_id == bot.id,
            BotOrder.status.in_(OPEN_ORDER_STATUSES),
        )
    ).first()
    if has_open_orders is None:
        return CancelOpenOrdersResult()

    api_key = decrypt(account.api_key_enc, settings.ENCRYPTION_KEY)
    api_secret = decrypt(account.api_secret_enc, settings.ENCRYPTION_KEY)
    extra_params: dict | None = None
    if account.extra_params_enc:
        extra_params = json.loads(
            decrypt(account.extra_params_enc, settings.ENCRYPTION_KEY)
        )

    adapter = get_adapter(
        exchange=account.exchange,
        api_key=api_key,
        api_secret=api_secret,
        extra_params=extra_params,
    )
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            cancel_open_orders_with_adapter(
                session=session,
                bot_id=bot.id,
                adapter=adapter,
            )
        )
    finally:
        try:
            loop.run_until_complete(adapter.close())
        except Exception:
            pass
        loop.close()
