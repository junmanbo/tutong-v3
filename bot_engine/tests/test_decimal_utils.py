"""bot_engine/utils/decimal_utils.py 단위 테스트.

커버리지 목표: 100%
DB 불필요 — 순수 함수 테스트.
"""
import pytest
from decimal import Decimal

from bot_engine.utils.decimal_utils import (
    apply_lot_size,
    calculate_grid_prices,
    calculate_pnl,
    qty_from_amount,
    round_price,
    to_decimal,
)


# ── to_decimal ────────────────────────────────────────────────────────────────


class TestToDecimal:
    def test_none_returns_default(self):
        assert to_decimal(None) == Decimal("0")

    def test_none_with_custom_default(self):
        assert to_decimal(None, default="1.5") == Decimal("1.5")

    def test_float_preserves_value(self):
        # str 경유이므로 float 정밀도 손실 없음
        result = to_decimal(0.1)
        assert result == Decimal("0.1")

    def test_float_67230_5(self):
        assert to_decimal(67230.5) == Decimal("67230.5")

    def test_string_input(self):
        assert to_decimal("123.456") == Decimal("123.456")

    def test_int_input(self):
        assert to_decimal(100) == Decimal("100")

    def test_zero(self):
        assert to_decimal(0) == Decimal("0")

    def test_negative(self):
        assert to_decimal(-1.5) == Decimal("-1.5")

    def test_very_small(self):
        assert to_decimal("0.00000001") == Decimal("0.00000001")

    def test_returns_decimal_type(self):
        assert isinstance(to_decimal(1.0), Decimal)


# ── apply_lot_size ────────────────────────────────────────────────────────────


class TestApplyLotSize:
    def test_exact_multiple(self):
        assert apply_lot_size(Decimal("1.000"), "0.001") == Decimal("1.000")

    def test_rounds_down(self):
        assert apply_lot_size(Decimal("1.0019"), "0.001") == Decimal("1.001")

    def test_large_step(self):
        assert apply_lot_size(Decimal("1.9"), "1") == Decimal("1")

    def test_small_step_satoshi(self):
        qty = Decimal("0.123456789")
        result = apply_lot_size(qty, "0.00000001")
        assert result == Decimal("0.12345678")

    def test_zero_qty(self):
        assert apply_lot_size(Decimal("0"), "0.001") == Decimal("0")

    def test_step_001(self):
        # 0.0159 // 0.01 = 1 * 0.01 = 0.01
        assert apply_lot_size(Decimal("0.0159"), "0.01") == Decimal("0.01")

    def test_result_is_always_less_or_equal_original(self):
        qty = Decimal("5.123456")
        result = apply_lot_size(qty, "0.001")
        assert result <= qty


# ── calculate_pnl ─────────────────────────────────────────────────────────────


class TestCalculatePnl:
    def test_profit(self):
        pnl, pct = calculate_pnl(
            buy_price=Decimal("50000"),
            sell_price=Decimal("55000"),
            qty=Decimal("0.01"),
        )
        assert pnl == Decimal("50")
        assert pct == Decimal("10.0000")

    def test_loss(self):
        pnl, pct = calculate_pnl(
            buy_price=Decimal("50000"),
            sell_price=Decimal("45000"),
            qty=Decimal("0.01"),
        )
        assert pnl == Decimal("-50")
        assert pct == Decimal("-10.0000")

    def test_breakeven(self):
        pnl, pct = calculate_pnl(
            buy_price=Decimal("100"),
            sell_price=Decimal("100"),
            qty=Decimal("1"),
        )
        assert pnl == Decimal("0")
        assert pct == Decimal("0.0000")

    def test_zero_buy_price_returns_zero_pct(self):
        pnl, pct = calculate_pnl(
            buy_price=Decimal("0"),
            sell_price=Decimal("100"),
            qty=Decimal("1"),
        )
        assert pct == Decimal("0")

    def test_pct_precision_rounding(self):
        # 1/3 * 100 = 33.3333...% → ROUND_HALF_UP → 33.3333
        pnl, pct = calculate_pnl(
            buy_price=Decimal("3"),
            sell_price=Decimal("4"),
            qty=Decimal("1"),
        )
        assert pct == Decimal("33.3333")

    def test_pnl_tuple_has_two_elements(self):
        result = calculate_pnl(Decimal("100"), Decimal("110"), Decimal("1"))
        assert len(result) == 2


# ── calculate_grid_prices ─────────────────────────────────────────────────────


class TestCalculateGridPrices:
    def test_arithmetic_grid_count_prices(self):
        prices = calculate_grid_prices(
            upper=Decimal("200"),
            lower=Decimal("100"),
            grid_count=4,
        )
        assert len(prices) == 5
        assert prices[0] == Decimal("100")
        assert prices[-1] == Decimal("200")

    def test_arithmetic_step_equal(self):
        prices = calculate_grid_prices(
            upper=Decimal("100"),
            lower=Decimal("0"),
            grid_count=10,
        )
        step = prices[1] - prices[0]
        for i in range(1, len(prices)):
            assert prices[i] - prices[i - 1] == step

    def test_arithmetic_grid_2(self):
        prices = calculate_grid_prices(Decimal("200"), Decimal("100"), 2)
        assert len(prices) == 3
        assert prices[1] == Decimal("150")

    def test_geometric_grid(self):
        prices = calculate_grid_prices(
            upper=Decimal("200"),
            lower=Decimal("100"),
            grid_count=2,
            arithmetic=False,
        )
        assert len(prices) == 3
        assert prices[0] == Decimal("100")
        # 등비이므로 첫번째 비율 == 두번째 비율
        ratio1 = prices[1] / prices[0]
        ratio2 = prices[2] / prices[1]
        assert abs(ratio1 - ratio2) < Decimal("0.0001")

    def test_raises_if_grid_count_less_than_2(self):
        with pytest.raises(ValueError, match="grid_count must be >= 2"):
            calculate_grid_prices(Decimal("200"), Decimal("100"), 1)

    def test_raises_if_upper_not_greater_than_lower(self):
        with pytest.raises(ValueError, match="upper must be greater than lower"):
            calculate_grid_prices(Decimal("100"), Decimal("200"), 4)

    def test_raises_if_upper_equals_lower(self):
        with pytest.raises(ValueError, match="upper must be greater than lower"):
            calculate_grid_prices(Decimal("100"), Decimal("100"), 4)


# ── qty_from_amount ───────────────────────────────────────────────────────────


class TestQtyFromAmount:
    def test_basic(self):
        # 100 USDT / 50000 = 0.002 BTC, step 0.001 → 0.002
        result = qty_from_amount(Decimal("100"), Decimal("50000"), "0.001")
        assert result == Decimal("0.002")

    def test_truncates_via_lot_size(self):
        # 100 / 3 = 33.333..., step 1 → 33
        result = qty_from_amount(Decimal("100"), Decimal("3"), "1")
        assert result == Decimal("33")

    def test_zero_price_returns_zero(self):
        result = qty_from_amount(Decimal("100"), Decimal("0"), "0.001")
        assert result == Decimal("0")

    def test_result_less_or_equal_amount_divided_by_price(self):
        amount = Decimal("1000")
        price = Decimal("67230.5")
        step = "0.001"
        result = qty_from_amount(amount, price, step)
        assert result * price <= amount


# ── round_price ───────────────────────────────────────────────────────────────


class TestRoundPrice:
    def test_tick_1(self):
        assert round_price(Decimal("67230.7"), "1") == Decimal("67230")

    def test_tick_001(self):
        assert round_price(Decimal("1234.5678"), "0.01") == Decimal("1234.56")

    def test_already_exact(self):
        assert round_price(Decimal("100.00"), "0.01") == Decimal("100.00")

    def test_tick_10(self):
        assert round_price(Decimal("1259"), "10") == Decimal("1250")

    def test_always_floors(self):
        # 절대 올림하지 않음
        assert round_price(Decimal("99.999"), "1") == Decimal("99")
