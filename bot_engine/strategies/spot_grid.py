"""Spot Grid 전략 핵심 로직 (순수 함수).

exchange adapter에 의존하지 않고, 가격/그리드 상태를 입력받아
주문 결정만 반환합니다.

bot.config 예시:
    {
        "upper": "50000",          # 상한가
        "lower": "40000",          # 하한가
        "grid_count": 10,          # 그리드 수
        "amount_per_grid": "100",  # 그리드당 투자 금액 (quote)
        "arithmetic": true,        # true=등간격, false=등비
        "step_size": "0.00001",    # 거래소 stepSize
        "tick_size": "0.01"        # 거래소 tickSize
    }
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from bot_engine.utils.decimal_utils import (
    calculate_grid_prices,
    qty_from_amount,
    round_price,
    to_decimal,
)


@dataclass
class GridLevel:
    """그리드 레벨 하나."""

    price: Decimal
    qty: Decimal
    side: str           # "buy" | "sell"
    order_id: str | None = None  # 거래소 주문 ID (미배치: None)
    filled: bool = False


@dataclass(frozen=True)
class GridConfig:
    """Spot Grid 봇 설정."""

    symbol: str
    upper: Decimal
    lower: Decimal
    grid_count: int
    amount_per_grid: Decimal
    arithmetic: bool = True
    step_size: str = "0.00001"
    tick_size: str = "0.01"

    @classmethod
    def from_dict(cls, symbol: str, config: dict) -> "GridConfig":
        return cls(
            symbol=symbol,
            upper=to_decimal(config.get("upper", "0")),
            lower=to_decimal(config.get("lower", "0")),
            grid_count=int(config.get("grid_count", 10)),
            amount_per_grid=to_decimal(config.get("amount_per_grid", "100")),
            arithmetic=bool(config.get("arithmetic", True)),
            step_size=config.get("step_size", "0.00001"),
            tick_size=config.get("tick_size", "0.01"),
        )


def build_grid(config: GridConfig) -> list[GridLevel]:
    """그리드 매수 레벨 초기화.

    상한가를 제외한 모든 레벨에 매수 주문을 배치합니다.
    체결되면 바로 위 레벨에 매도 주문을 자동 생성합니다.

    Args:
        config: 그리드 설정

    Returns:
        그리드 레벨 리스트 (가격 오름차순)
    """
    prices = calculate_grid_prices(
        config.upper, config.lower, config.grid_count, config.arithmetic
    )
    levels: list[GridLevel] = []
    for price in prices[:-1]:  # 상한가 제외 (매수 레벨만)
        adjusted = round_price(price, config.tick_size)
        qty = qty_from_amount(config.amount_per_grid, adjusted, config.step_size)
        if qty > Decimal("0"):
            levels.append(GridLevel(price=adjusted, qty=qty, side="buy"))
    return levels


def get_buy_prices(levels: list[GridLevel]) -> list[Decimal]:
    """매수 레벨 가격 목록 (오름차순)."""
    return sorted({lv.price for lv in levels if lv.side == "buy"})


def on_buy_filled(
    filled_level: GridLevel,
    levels: list[GridLevel],
) -> GridLevel | None:
    """매수 체결 처리 — 바로 위 레벨에 매도 주문 생성.

    Args:
        filled_level: 체결된 매수 레벨
        levels: 전체 그리드 레벨 리스트 (변경됨)

    Returns:
        새로 생성된 매도 레벨 (상한가 초과 시 None)
    """
    filled_level.filled = True

    buy_prices = get_buy_prices(levels)
    try:
        idx = buy_prices.index(filled_level.price)
    except ValueError:
        return None

    if idx + 1 >= len(buy_prices):
        return None  # 최상단 레벨 → 매도 레벨 없음

    sell_price = buy_prices[idx + 1]
    sell_level = GridLevel(price=sell_price, qty=filled_level.qty, side="sell")
    levels.append(sell_level)
    return sell_level


def on_sell_filled(
    filled_level: GridLevel,
    levels: list[GridLevel],
) -> GridLevel | None:
    """매도 체결 처리 — 바로 아래 레벨에 매수 주문 재생성.

    Args:
        filled_level: 체결된 매도 레벨
        levels: 전체 그리드 레벨 리스트 (변경됨)

    Returns:
        재생성된 매수 레벨 (최하단 레벨이면 None)
    """
    filled_level.filled = True

    buy_prices = get_buy_prices(levels)
    try:
        idx = buy_prices.index(filled_level.price)
    except ValueError:
        return None

    if idx <= 0:
        return None  # 최하단 레벨 → 재매수 없음

    buy_price = buy_prices[idx - 1]
    buy_level = GridLevel(price=buy_price, qty=filled_level.qty, side="buy")
    levels.append(buy_level)
    return buy_level


def calc_grid_profit(buy_price: Decimal, sell_price: Decimal, qty: Decimal) -> Decimal:
    """그리드 1회전 순수익 계산."""
    return (sell_price - buy_price) * qty
