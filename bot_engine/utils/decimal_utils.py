"""금융 계산 유틸리티.

모든 금융 계산은 Decimal을 사용합니다. float 사용 금지.
테스트 커버리지 목표: 100%
"""
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal


def to_decimal(value: float | str | int | None, default: str = "0") -> Decimal:
    """float/str → Decimal 안전 변환 (str 경유 필수).

    Args:
        value: 변환할 값 (None 허용)
        default: None 또는 변환 불가 시 기본값

    Returns:
        Decimal 값
    """
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


def apply_lot_size(qty: Decimal, step_size: str) -> Decimal:
    """거래소 Lot Size(stepSize) 적용 — 항상 내림 처리.

    초과 주문 방지를 위해 내림 처리합니다.

    Args:
        qty: 원본 수량
        step_size: 거래소 stepSize 문자열 (예: "0.001", "0.00000001")

    Returns:
        Lot Size가 적용된 수량
    """
    step = Decimal(step_size)
    return (qty // step) * step


def calculate_pnl(
    buy_price: Decimal,
    sell_price: Decimal,
    qty: Decimal,
) -> tuple[Decimal, Decimal]:
    """수익금 및 수익률 계산.

    Args:
        buy_price: 매수 단가
        sell_price: 매도 단가
        qty: 수량

    Returns:
        (pnl: 수익금, pct: 수익률 %)
    """
    pnl = (sell_price - buy_price) * qty
    if buy_price == Decimal("0"):
        pct = Decimal("0")
    else:
        pct = ((sell_price - buy_price) / buy_price * 100).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
    return pnl, pct


def calculate_grid_prices(
    upper: Decimal,
    lower: Decimal,
    grid_count: int,
    arithmetic: bool = True,
) -> list[Decimal]:
    """그리드 가격 리스트 계산.

    Args:
        upper: 상한가
        lower: 하한가
        grid_count: 그리드 수 (2 ~ 200)
        arithmetic: True=등간격, False=등비

    Returns:
        하한가부터 상한가까지의 그리드 가격 리스트 (grid_count + 1개)
    """
    if grid_count < 2:
        raise ValueError("grid_count must be >= 2")
    if upper <= lower:
        raise ValueError("upper must be greater than lower")

    prices: list[Decimal] = []
    if arithmetic:
        step = (upper - lower) / grid_count
        for i in range(grid_count + 1):
            prices.append(lower + step * i)
    else:
        # 등비 그리드: ratio = (upper/lower)^(1/grid_count)
        ratio = (upper / lower) ** (Decimal("1") / Decimal(str(grid_count)))
        price = lower
        for _ in range(grid_count + 1):
            prices.append(price)
            price = price * ratio
    return prices


def qty_from_amount(amount: Decimal, price: Decimal, step_size: str) -> Decimal:
    """투자 금액과 가격으로 주문 수량 계산 (내림 + Lot Size 적용).

    Args:
        amount: 투자 금액
        price: 주문 가격
        step_size: 거래소 stepSize 문자열

    Returns:
        Lot Size가 적용된 주문 수량
    """
    if price == Decimal("0"):
        return Decimal("0")
    raw_qty = amount / price
    return apply_lot_size(raw_qty, step_size)


def round_price(price: Decimal, tick_size: str) -> Decimal:
    """가격을 거래소 tick_size에 맞게 내림 처리.

    Args:
        price: 원본 가격
        tick_size: 거래소 tick_size 문자열 (예: "0.01", "1")

    Returns:
        tick_size가 적용된 가격
    """
    tick = Decimal(tick_size)
    return (price // tick) * tick
