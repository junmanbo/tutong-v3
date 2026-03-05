"""Position Snowball 전략 핵심 로직 (순수 함수).

exchange adapter에 의존하지 않고, 가격/매수 이력을 입력받아
매수/익절 결정만 반환합니다.

bot.config 예시:
    {
        "drop_pct": "5",           # 마지막 매수가 대비 하락률 (%) 시 추가 매수
        "amount_per_buy": "100",   # 회당 매수 금액 (quote)
        "take_profit_pct": "3",    # 평균 매입가 대비 수익률 (%) 시 전량 익절
        "max_buys": 5,             # 최대 매수 횟수 (리스크 제한)
        "step_size": "0.00001"     # 거래소 stepSize
    }
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from bot_engine.utils.decimal_utils import qty_from_amount, to_decimal


@dataclass(frozen=True)
class SnowballConfig:
    """Position Snowball 봇 설정."""

    symbol: str
    drop_pct: Decimal         # 추가 매수 하락 기준 (%)
    amount_per_buy: Decimal   # 회당 매수 금액 (quote)
    take_profit_pct: Decimal  # 익절 수익률 기준 (%)
    max_buys: int             # 최대 매수 횟수
    step_size: str            # 거래소 stepSize

    @classmethod
    def from_dict(cls, symbol: str, config: dict) -> "SnowballConfig":
        return cls(
            symbol=symbol,
            drop_pct=to_decimal(config.get("drop_pct", "5")),
            amount_per_buy=to_decimal(config.get("amount_per_buy", "100")),
            take_profit_pct=to_decimal(config.get("take_profit_pct", "3")),
            max_buys=int(config.get("max_buys", 5)),
            step_size=config.get("step_size", "0.00001"),
        )


@dataclass
class BuyRecord:
    """매수 이력 하나."""

    price: Decimal
    qty: Decimal


def should_add_buy(
    current_price: Decimal,
    last_buy_price: Decimal,
    drop_pct: Decimal,
) -> bool:
    """추가 매수 조건 확인.

    마지막 매수가 대비 drop_pct% 이상 하락 시 True.

    Args:
        current_price: 현재 시장가
        last_buy_price: 마지막 매수 가격
        drop_pct: 하락 기준 (%)
    """
    if last_buy_price <= Decimal("0"):
        return False
    drop = (last_buy_price - current_price) / last_buy_price * 100
    return drop >= drop_pct


def should_take_profit(
    current_price: Decimal,
    avg_buy_price: Decimal,
    take_profit_pct: Decimal,
) -> bool:
    """익절 조건 확인.

    평균 매입가 대비 take_profit_pct% 이상 상승 시 True.

    Args:
        current_price: 현재 시장가
        avg_buy_price: 평균 매입가
        take_profit_pct: 익절 기준 (%)
    """
    if avg_buy_price <= Decimal("0"):
        return False
    gain = (current_price - avg_buy_price) / avg_buy_price * 100
    return gain >= take_profit_pct


def calc_avg_price(buys: list[BuyRecord]) -> Decimal:
    """수량 가중 평균 매입가 계산.

    Args:
        buys: 매수 이력 리스트

    Returns:
        평균 매입가 (매수 없으면 Decimal("0"))
    """
    if not buys:
        return Decimal("0")
    total_cost = sum(b.price * b.qty for b in buys)
    total_qty = sum(b.qty for b in buys)
    if total_qty == Decimal("0"):
        return Decimal("0")
    return total_cost / total_qty


def calc_total_qty(buys: list[BuyRecord]) -> Decimal:
    """총 보유 수량 계산."""
    return sum(b.qty for b in buys)


def calc_buy_qty(amount: Decimal, price: Decimal, step_size: str) -> Decimal:
    """매수 금액으로 주문 수량 계산."""
    return qty_from_amount(amount, price, step_size)
