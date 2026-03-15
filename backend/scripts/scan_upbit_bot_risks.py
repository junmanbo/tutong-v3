from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlmodel import Session, select

from app.core.db import engine
from app.models import Bot, BotOrder, BotTypeEnum, ExchangeAccount, ExchangeTypeEnum, User

UPBIT_MIN_ORDER_KRW = Decimal("5000")


def to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def order_amount_for_bot(bot: Bot) -> tuple[str, Decimal] | None:
    config = bot.config or {}

    if bot.bot_type == BotTypeEnum.spot_grid:
        return "amount_per_grid", to_decimal(config.get("amount_per_grid"))
    if bot.bot_type == BotTypeEnum.spot_dca:
        return "amount_per_order", to_decimal(config.get("amount_per_order"))
    if bot.bot_type == BotTypeEnum.position_snowball:
        return "amount_per_buy", to_decimal(config.get("amount_per_buy"))
    return None


def main() -> int:
    with Session(engine) as session:
        statement = (
            select(Bot, ExchangeAccount, User)
            .join(ExchangeAccount, ExchangeAccount.id == Bot.account_id)
            .join(User, User.id == Bot.user_id)
            .where(
                Bot.deleted_at.is_(None),
                ExchangeAccount.deleted_at.is_(None),
                ExchangeAccount.exchange == ExchangeTypeEnum.upbit,
            )
            .order_by(User.email, Bot.created_at.desc())
        )
        rows = session.exec(statement).all()

        risky_rows: list[dict[str, str]] = []
        for bot, account, user in rows:
            if not bot.symbol or not bot.symbol.upper().endswith("/KRW"):
                continue

            amount_info = order_amount_for_bot(bot)
            if amount_info is None:
                continue

            field_name, order_amount = amount_info
            if order_amount >= UPBIT_MIN_ORDER_KRW:
                continue

            order_count = len(
                session.exec(select(BotOrder.id).where(BotOrder.bot_id == bot.id)).all()
            )
            risky_rows.append(
                {
                    "user": user.email,
                    "bot_name": bot.name,
                    "bot_type": bot.bot_type.value,
                    "status": bot.status.value,
                    "symbol": bot.symbol,
                    "account": account.label,
                    "field": field_name,
                    "amount": f"{order_amount.normalize()} KRW",
                    "orders": str(order_count),
                    "bot_id": str(bot.id),
                }
            )

    print("Upbit KRW bots with risky minimum-order configuration")
    print(f"Rule: per-order amount must be >= {UPBIT_MIN_ORDER_KRW} KRW")
    print()

    if not risky_rows:
        print("No risky bots found.")
        return 0

    for row in risky_rows:
        print(
            " | ".join(
                [
                    row["user"],
                    row["bot_name"],
                    row["bot_type"],
                    row["status"],
                    row["symbol"],
                    row["account"],
                    f'{row["field"]}={row["amount"]}',
                    f'orders={row["orders"]}',
                    row["bot_id"],
                ]
            )
        )

    print()
    print(f"Found {len(risky_rows)} risky bot(s).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
