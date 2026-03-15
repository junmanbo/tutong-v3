from __future__ import annotations

from decimal import Decimal

from app.models import BotTypeEnum, ExchangeTypeEnum

UPBIT_MIN_ORDER_KRW = Decimal("5000")


class BotValidationError(ValueError):
    """봇 설정이 거래소 제약을 만족하지 않을 때 발생."""


def get_quote_currency(symbol: str | None) -> str | None:
    if not symbol or "/" not in symbol:
        return None
    _, quote = symbol.split("/", 1)
    return quote.upper()


def validate_bot_configuration(
    *,
    bot_type: BotTypeEnum,
    exchange: ExchangeTypeEnum,
    symbol: str | None,
    config: dict | None,
) -> None:
    """거래소/전략 조합에 맞는 봇 설정을 검증한다."""
    if exchange != ExchangeTypeEnum.upbit:
        return

    quote_currency = get_quote_currency(symbol)
    if quote_currency != "KRW":
        return

    config = config or {}

    if bot_type == BotTypeEnum.spot_grid:
        _validate_min_quote_amount(
            amount=Decimal(str(config.get("amount_per_grid", "0"))),
            field_name="amount_per_grid",
            context="Spot Grid",
        )
        return

    if bot_type == BotTypeEnum.spot_dca:
        _validate_min_quote_amount(
            amount=Decimal(str(config.get("amount_per_order", "0"))),
            field_name="amount_per_order",
            context="Spot DCA",
        )
        return

    if bot_type == BotTypeEnum.position_snowball:
        _validate_min_quote_amount(
            amount=Decimal(str(config.get("amount_per_buy", "0"))),
            field_name="amount_per_buy",
            context="Position Snowball",
        )


def _validate_min_quote_amount(
    *,
    amount: Decimal,
    field_name: str,
    context: str,
) -> None:
    if amount < UPBIT_MIN_ORDER_KRW:
        raise BotValidationError(
            f"{context} on Upbit requires `{field_name}` >= "
            f"{UPBIT_MIN_ORDER_KRW} KRW."
        )
