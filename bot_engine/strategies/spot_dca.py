"""Spot DCA 전략 핵심 로직 (순수 함수).

exchange adapter에 의존하지 않고, 시간/가격/설정 데이터를 입력받아
주문 결정만 반환합니다.

bot.config 예시:
    {
        "amount_per_order": "100",   # 매수 금액 (quote currency)
        "interval_seconds": 86400,   # 매수 주기 (초), 기본 1일
        "order_type": "market",      # "market" | "limit"
        "total_orders": 30,          # 총 매수 횟수 (없으면 무한)
        "step_size": "0.00001"       # 거래소 stepSize
    }
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from bot_engine.utils.decimal_utils import qty_from_amount, to_decimal

UTC = timezone.utc


@dataclass(frozen=True)
class DcaConfig:
    """Spot DCA 봇 설정."""

    symbol: str
    amount_per_order: Decimal  # 매수 금액 (quote currency)
    interval_seconds: int      # 매수 주기 (초)
    order_type: str            # "market" | "limit"
    total_orders: int | None   # 총 매수 횟수 (None = 무한)
    step_size: str             # 거래소 stepSize

    @classmethod
    def from_dict(cls, symbol: str, config: dict) -> "DcaConfig":
        return cls(
            symbol=symbol,
            amount_per_order=to_decimal(config.get("amount_per_order", "100")),
            interval_seconds=int(config.get("interval_seconds", 86400)),
            order_type=config.get("order_type", "market"),
            total_orders=int(config["total_orders"]) if config.get("total_orders") else None,
            step_size=config.get("step_size", "0.00001"),
        )


def should_buy(
    last_order_time: datetime | None,
    interval_seconds: int,
    now: datetime | None = None,
) -> bool:
    """다음 매수 타이밍인지 확인.

    Args:
        last_order_time: 마지막 매수 시각 (None이면 즉시 매수)
        interval_seconds: 매수 주기 (초)
        now: 현재 시각 (기본값: UTC now)

    Returns:
        True면 매수 실행
    """
    if last_order_time is None:
        return True
    if now is None:
        now = datetime.now(UTC)
    # timezone-aware 비교를 위해 last_order_time이 naive면 UTC로 간주
    if last_order_time.tzinfo is None:
        last_order_time = last_order_time.replace(tzinfo=UTC)
    return (now - last_order_time).total_seconds() >= interval_seconds


def calc_order_qty(amount: Decimal, price: Decimal, step_size: str) -> Decimal:
    """투자 금액과 현재가로 주문 수량 계산 (Lot Size 적용).

    Args:
        amount: 투자 금액 (quote currency)
        price: 현재 시장가
        step_size: 거래소 stepSize

    Returns:
        Lot Size가 적용된 주문 수량
    """
    return qty_from_amount(amount, price, step_size)


def is_completed(order_count: int, total_orders: int | None) -> bool:
    """매수 횟수 완료 여부.

    Args:
        order_count: 실행된 매수 횟수
        total_orders: 목표 매수 횟수 (None = 무한)
    """
    return total_orders is not None and order_count >= total_orders
