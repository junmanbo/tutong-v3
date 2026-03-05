"""Algo Orders (TWAP) 전략 테스트."""
from decimal import Decimal

import pytest

from bot_engine.strategies.algo_orders import (
    AlgoConfig,
    calc_interval,
    calc_remaining_qty,
    calc_slice_qty,
    is_completed,
)


# ── AlgoConfig.from_dict ───────────────────────────────────────────────────────


class TestAlgoConfigFromDict:
    def test_defaults(self):
        cfg = AlgoConfig.from_dict("BTC/USDT", {})
        assert cfg.symbol == "BTC/USDT"
        assert cfg.side == "buy"
        assert cfg.total_qty == Decimal("1")
        assert cfg.num_slices == 10
        assert cfg.duration_seconds == 3600
        assert cfg.order_type == "market"
        assert cfg.step_size == "0.00001"

    def test_custom_values(self):
        cfg = AlgoConfig.from_dict(
            "ETH/USDT",
            {
                "side": "sell",
                "total_qty": "5.5",
                "num_slices": 20,
                "duration_seconds": 7200,
                "order_type": "limit",
                "step_size": "0.001",
            },
        )
        assert cfg.side == "sell"
        assert cfg.total_qty == Decimal("5.5")
        assert cfg.num_slices == 20
        assert cfg.duration_seconds == 7200
        assert cfg.order_type == "limit"
        assert cfg.step_size == "0.001"


# ── calc_slice_qty ─────────────────────────────────────────────────────────────


class TestCalcSliceQty:
    def test_basic_division(self):
        # 1.0 / 10 = 0.1, step 0.00001 → 0.10000
        qty = calc_slice_qty(Decimal("1"), 10, "0.00001")
        assert qty == Decimal("0.10000")

    def test_rounds_down_not_up(self):
        # 1.0 / 3 = 0.3333... → step 0.001 → 0.333 (내림)
        qty = calc_slice_qty(Decimal("1"), 3, "0.001")
        assert qty == Decimal("0.333")

    def test_zero_slices_returns_zero(self):
        qty = calc_slice_qty(Decimal("1"), 0, "0.001")
        assert qty == Decimal("0")

    def test_negative_slices_returns_zero(self):
        qty = calc_slice_qty(Decimal("1"), -1, "0.001")
        assert qty == Decimal("0")

    def test_one_slice_equals_total(self):
        qty = calc_slice_qty(Decimal("1.5"), 1, "0.001")
        assert qty == Decimal("1.500")

    def test_large_slice_count(self):
        # 1.0 / 100 = 0.01, step 0.001 → 0.010
        qty = calc_slice_qty(Decimal("1"), 100, "0.001")
        assert qty == Decimal("0.010")

    def test_step_size_applied(self):
        # 10 / 3 = 3.333... → step 1 → 3
        qty = calc_slice_qty(Decimal("10"), 3, "1")
        assert qty == Decimal("3")

    def test_exact_division(self):
        # 1.0 / 4 = 0.25, step 0.01 → 0.25
        qty = calc_slice_qty(Decimal("1"), 4, "0.01")
        assert qty == Decimal("0.25")


# ── calc_remaining_qty ─────────────────────────────────────────────────────────


class TestCalcRemainingQty:
    def test_remaining_after_partial_execution(self):
        # total=1.0, slice=0.333, executed=2 → remaining = 1.0 - 0.666 = 0.334
        remaining = calc_remaining_qty(
            Decimal("1"), Decimal("0.333"), 2, "0.001"
        )
        assert remaining == Decimal("0.334")

    def test_remaining_for_last_slice(self):
        # total=1.0, slice=0.1, executed=9 → remaining = 0.1
        remaining = calc_remaining_qty(
            Decimal("1"), Decimal("0.1"), 9, "0.00001"
        )
        assert remaining == Decimal("0.10000")

    def test_remaining_zero_when_fully_executed(self):
        remaining = calc_remaining_qty(
            Decimal("1"), Decimal("0.1"), 10, "0.001"
        )
        assert remaining == Decimal("0")

    def test_remaining_zero_when_over_executed(self):
        remaining = calc_remaining_qty(
            Decimal("1"), Decimal("0.1"), 11, "0.001"
        )
        assert remaining == Decimal("0")

    def test_step_size_applied_to_remaining(self):
        # total=1.0, slice=0.333, executed=2 → raw remaining=0.334 → step 0.01 → 0.33
        remaining = calc_remaining_qty(
            Decimal("1"), Decimal("0.333"), 2, "0.01"
        )
        assert remaining == Decimal("0.33")

    def test_first_slice_remaining(self):
        # total=1.0, executed=0 → remaining = 1.0 전체
        remaining = calc_remaining_qty(
            Decimal("1"), Decimal("0.1"), 0, "0.00001"
        )
        assert remaining == Decimal("1.00000")


# ── calc_interval ──────────────────────────────────────────────────────────────


class TestCalcInterval:
    def test_basic_interval(self):
        # 3600초 / (10-1) = 400초
        assert calc_interval(3600, 10) == 400

    def test_one_slice_returns_zero(self):
        assert calc_interval(3600, 1) == 0

    def test_zero_slices_returns_zero(self):
        assert calc_interval(3600, 0) == 0

    def test_two_slices(self):
        # 3600 / (2-1) = 3600
        assert calc_interval(3600, 2) == 3600

    def test_integer_division(self):
        # 3600 / (7-1) = 600
        assert calc_interval(3600, 7) == 600

    def test_truncates_remainder(self):
        # 100 / (3-1) = 50
        assert calc_interval(100, 3) == 50

    def test_large_duration(self):
        # 86400 / (24-1) = 3756 (정수 나눗셈)
        assert calc_interval(86400, 24) == 3756

    def test_one_second_duration(self):
        assert calc_interval(1, 2) == 1


# ── is_completed ───────────────────────────────────────────────────────────────


class TestIsCompleted:
    def test_not_completed_when_below(self):
        assert is_completed(9, 10) is False

    def test_completed_when_equal(self):
        assert is_completed(10, 10) is True

    def test_completed_when_exceeds(self):
        assert is_completed(11, 10) is True

    def test_zero_executed_not_completed(self):
        assert is_completed(0, 10) is False

    def test_zero_total_immediately_done(self):
        assert is_completed(0, 0) is True

    def test_one_slice_completes_immediately(self):
        assert is_completed(1, 1) is True


# ── 통합: slice_qty + remaining_qty 합산 = total_qty ──────────────────────────


class TestSliceQtyIntegration:
    def test_all_slices_sum_to_total(self):
        """slice_qty * (n-1) + remaining_qty = total_qty 검증."""
        total = Decimal("1")
        num_slices = 3
        step_size = "0.001"
        slice_qty = calc_slice_qty(total, num_slices, step_size)
        # 0.333 * 2 = 0.666
        remaining = calc_remaining_qty(total, slice_qty, num_slices - 1, step_size)
        executed_total = slice_qty * Decimal(str(num_slices - 1)) + remaining
        # 정밀도 오차 허용 (step_size 내림으로 인한 소량 손실)
        assert abs(executed_total - total) <= Decimal(step_size)

    def test_ten_slices_sum_close_to_total(self):
        total = Decimal("1")
        num_slices = 10
        step_size = "0.00001"
        slice_qty = calc_slice_qty(total, num_slices, step_size)
        remaining = calc_remaining_qty(total, slice_qty, num_slices - 1, step_size)
        executed_total = slice_qty * Decimal(str(num_slices - 1)) + remaining
        assert abs(executed_total - total) <= Decimal(step_size)
