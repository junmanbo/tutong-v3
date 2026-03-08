"""Rebalancing 전략 핵심 로직 (순수 함수).

exchange adapter에 의존하지 않고, 잔고/가격/목표비중을 입력받아
리밸런싱 주문 결정만 반환합니다.

bot.config 예시:
    {
        "assets": {"BTC": "50", "ETH": "30", "KRW": "20"},  # 목표 비중(%)
        "threshold_pct": "5",       # 리밸런싱 임계값 (%)
        "interval_seconds": 3600,   # 주기 체크 간격 (초)
        "quote": "KRW"              # 기준 통화
    }
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from bot_engine.utils.decimal_utils import to_decimal


@dataclass(frozen=True)
class RebalancingConfig:
    """Rebalancing 봇 설정."""

    assets: dict[str, Decimal]  # {"BTC": Decimal("50"), ...} 목표 비중(%)
    mode: str                   # "time" | "deviation"
    threshold_pct: Decimal       # 리밸런싱 임계값 (%)
    interval_seconds: int        # 주기 체크 간격 (초)
    quote: str                   # 기준 통화 (예: "KRW")

    @classmethod
    def from_dict(cls, config: dict) -> "RebalancingConfig":
        mode = str(config.get("mode", "deviation")).lower()
        if mode not in {"time", "deviation"}:
            mode = "deviation"
        return cls(
            assets={k: to_decimal(v) for k, v in config.get("assets", {}).items()},
            mode=mode,
            threshold_pct=to_decimal(config.get("threshold_pct", "5")),
            interval_seconds=max(1, int(config.get("interval_seconds", 3600))),
            quote=config.get("quote", "KRW"),
        )


@dataclass
class RebalanceOrder:
    """리밸런싱 주문 결정."""

    asset: str
    side: str        # "buy" | "sell"
    amount: Decimal  # quote 금액


def calc_weights(
    balances: dict[str, Decimal],
    prices: dict[str, Decimal],
    quote: str = "KRW",
) -> dict[str, Decimal]:
    """현재 자산 비중 계산 (quote 기준 가치 비율).

    Args:
        balances: {"BTC": Decimal("0.5"), "KRW": Decimal("5000"), ...}
        prices: {"BTC": Decimal("50000"), "ETH": Decimal("3000"), ...} (quote 기준)
        quote: 기준 통화

    Returns:
        {"BTC": Decimal("50.0"), ...} 형식의 비중 (%)
    """
    values: dict[str, Decimal] = {}
    for asset, qty in balances.items():
        if qty <= Decimal("0"):
            values[asset] = Decimal("0")
        elif asset == quote:
            values[asset] = qty
        elif asset in prices and prices[asset] > Decimal("0"):
            values[asset] = qty * prices[asset]
        else:
            values[asset] = Decimal("0")

    total = sum(values.values())
    if total == Decimal("0"):
        return {asset: Decimal("0") for asset in balances}

    return {asset: value / total * 100 for asset, value in values.items()}


def needs_rebalance(
    current_weights: dict[str, Decimal],
    target_weights: dict[str, Decimal],
    threshold_pct: Decimal,
) -> bool:
    """리밸런싱 필요 여부.

    어느 자산이라도 목표 비중과 threshold_pct% 이상 차이 나면 True.

    Args:
        current_weights: 현재 비중 (%)
        target_weights: 목표 비중 (%)
        threshold_pct: 허용 오차 (%)
    """
    for asset, target in target_weights.items():
        current = current_weights.get(asset, Decimal("0"))
        if abs(current - target) >= threshold_pct:
            return True
    return False


def calc_rebalance_orders(
    current_weights: dict[str, Decimal],
    target_weights: dict[str, Decimal],
    total_value: Decimal,
    quote: str = "KRW",
) -> list[RebalanceOrder]:
    """리밸런싱 주문 목록 계산.

    Args:
        current_weights: 현재 비중 (%)
        target_weights: 목표 비중 (%)
        total_value: 총 자산 가치 (quote)
        quote: 기준 통화 (주문 제외)

    Returns:
        실행할 리밸런싱 주문 목록 (quote 자산 제외)
    """
    orders: list[RebalanceOrder] = []
    for asset, target_pct in target_weights.items():
        if asset == quote:
            continue
        current_pct = current_weights.get(asset, Decimal("0"))
        diff_pct = target_pct - current_pct
        diff_value = total_value * diff_pct / 100

        if diff_value > Decimal("0"):
            orders.append(RebalanceOrder(asset=asset, side="buy", amount=diff_value))
        elif diff_value < Decimal("0"):
            orders.append(RebalanceOrder(asset=asset, side="sell", amount=abs(diff_value)))

    # 매도 먼저 실행 (quote 확보 후 매수)
    orders.sort(key=lambda o: 0 if o.side == "sell" else 1)
    return orders
