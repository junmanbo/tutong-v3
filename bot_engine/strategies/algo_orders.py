"""Algo Orders (TWAP) 전략 핵심 로직 (순수 함수).

exchange adapter에 의존하지 않고, 주문 설정을 입력받아
TWAP 슬라이스 계산만 수행합니다.

bot.config 예시:
    {
        "side": "buy",             # "buy" | "sell"
        "total_qty": "1.0",        # 총 주문 수량
        "num_slices": 10,          # 분할 횟수
        "duration_seconds": 3600,  # 총 실행 시간 (초)
        "order_type": "market",    # "market" | "limit"
        "step_size": "0.00001"     # 거래소 stepSize
    }
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from bot_engine.utils.decimal_utils import apply_lot_size, to_decimal


@dataclass(frozen=True)
class AlgoConfig:
    """Algo Orders 봇 설정."""

    symbol: str
    side: str            # "buy" | "sell"
    total_qty: Decimal
    num_slices: int
    duration_seconds: int
    order_type: str      # "market" | "limit"
    step_size: str       # 거래소 stepSize

    @classmethod
    def from_dict(cls, symbol: str, config: dict) -> "AlgoConfig":
        return cls(
            symbol=symbol,
            side=config.get("side", "buy"),
            total_qty=to_decimal(config.get("total_qty", "1")),
            num_slices=int(config.get("num_slices", 10)),
            duration_seconds=int(config.get("duration_seconds", 3600)),
            order_type=config.get("order_type", "market"),
            step_size=config.get("step_size", "0.00001"),
        )


def calc_slice_qty(total_qty: Decimal, num_slices: int, step_size: str) -> Decimal:
    """슬라이스당 주문 수량 계산 (Lot Size 적용, 내림).

    마지막 슬라이스에서 잔여 수량을 처리하므로 항상 내림 처리합니다.

    Args:
        total_qty: 총 주문 수량
        num_slices: 분할 횟수
        step_size: 거래소 stepSize

    Returns:
        슬라이스당 수량
    """
    if num_slices <= 0:
        return Decimal("0")
    raw = total_qty / Decimal(str(num_slices))
    return apply_lot_size(raw, step_size)


def calc_remaining_qty(
    total_qty: Decimal,
    slice_qty: Decimal,
    executed_slices: int,
    step_size: str,
) -> Decimal:
    """마지막 슬라이스 잔여 수량 계산 (Lot Size 적용).

    총 수량에서 기실행 수량을 뺀 값을 Lot Size에 맞게 조정합니다.

    Args:
        total_qty: 총 주문 수량
        slice_qty: 슬라이스당 수량
        executed_slices: 이미 실행된 슬라이스 수
        step_size: 거래소 stepSize
    """
    executed = slice_qty * Decimal(str(executed_slices))
    remaining = total_qty - executed
    if remaining <= Decimal("0"):
        return Decimal("0")
    return apply_lot_size(remaining, step_size)


def calc_interval(duration_seconds: int, num_slices: int) -> int:
    """슬라이스 간 대기 시간 계산 (초).

    Args:
        duration_seconds: 총 실행 시간 (초)
        num_slices: 분할 횟수

    Returns:
        슬라이스 간 간격 (초). 슬라이스가 1개 이하면 0.
    """
    if num_slices <= 1:
        return 0
    return duration_seconds // (num_slices - 1)


def is_completed(executed_slices: int, num_slices: int) -> bool:
    """모든 슬라이스 실행 완료 여부."""
    return executed_slices >= num_slices
