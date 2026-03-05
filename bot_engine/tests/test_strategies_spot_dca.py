"""Spot DCA 전략 테스트."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from bot_engine.strategies.spot_dca import (
    DcaConfig,
    calc_order_qty,
    is_completed,
    should_buy,
)

UTC = timezone.utc


# ── DcaConfig.from_dict ────────────────────────────────────────────────────────


class TestDcaConfigFromDict:
    def test_defaults(self):
        cfg = DcaConfig.from_dict("BTC/USDT", {})
        assert cfg.symbol == "BTC/USDT"
        assert cfg.amount_per_order == Decimal("100")
        assert cfg.interval_seconds == 86400
        assert cfg.order_type == "market"
        assert cfg.total_orders is None
        assert cfg.step_size == "0.00001"

    def test_custom_values(self):
        cfg = DcaConfig.from_dict(
            "ETH/USDT",
            {
                "amount_per_order": "500",
                "interval_seconds": 3600,
                "order_type": "limit",
                "total_orders": 30,
                "step_size": "0.001",
            },
        )
        assert cfg.symbol == "ETH/USDT"
        assert cfg.amount_per_order == Decimal("500")
        assert cfg.interval_seconds == 3600
        assert cfg.order_type == "limit"
        assert cfg.total_orders == 30
        assert cfg.step_size == "0.001"

    def test_total_orders_none_when_missing(self):
        cfg = DcaConfig.from_dict("BTC/USDT", {"total_orders": 0})
        # 0은 falsy → None으로 처리
        assert cfg.total_orders is None

    def test_total_orders_set_when_positive(self):
        cfg = DcaConfig.from_dict("BTC/USDT", {"total_orders": 1})
        assert cfg.total_orders == 1


# ── should_buy ─────────────────────────────────────────────────────────────────


class TestShouldBuy:
    def test_buy_immediately_when_no_last_order(self):
        assert should_buy(None, 86400) is True

    def test_buy_when_interval_elapsed(self):
        last = datetime.now(UTC) - timedelta(seconds=86401)
        assert should_buy(last, 86400) is True

    def test_no_buy_when_interval_not_elapsed(self):
        last = datetime.now(UTC) - timedelta(seconds=3600)
        assert should_buy(last, 86400) is False

    def test_buy_when_exactly_at_interval(self):
        now = datetime.now(UTC)
        last = now - timedelta(seconds=3600)
        assert should_buy(last, 3600, now) is True

    def test_no_buy_when_one_second_short(self):
        now = datetime.now(UTC)
        last = now - timedelta(seconds=3599)
        assert should_buy(last, 3600, now) is False

    def test_naive_datetime_treated_as_utc(self):
        """tzinfo 없는 datetime은 UTC로 간주해야 함."""
        last_naive = (datetime.now(UTC) - timedelta(seconds=100000)).replace(
            tzinfo=None
        )
        assert should_buy(last_naive, 86400) is True

    def test_naive_datetime_recent_no_buy(self):
        last_naive = (datetime.now(UTC) - timedelta(seconds=60)).replace(tzinfo=None)
        assert should_buy(last_naive, 86400) is False

    def test_custom_now_parameter(self):
        fixed_now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        last = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)  # 12시간 전
        assert should_buy(last, 43200, fixed_now) is True  # 정확히 12h
        assert should_buy(last, 43201, fixed_now) is False  # 1초 부족


# ── calc_order_qty ─────────────────────────────────────────────────────────────


class TestCalcOrderQty:
    def test_basic_market_buy(self):
        # 100 USDT, 50000 USDT/BTC, step 0.00001
        qty = calc_order_qty(Decimal("100"), Decimal("50000"), "0.00001")
        assert qty == Decimal("0.00200")  # 100/50000 = 0.002, step 0.00001 → 0.00200

    def test_step_size_applied(self):
        # 100 / 3 = 33.333... → step 1 → 33
        qty = calc_order_qty(Decimal("100"), Decimal("3"), "1")
        assert qty == Decimal("33")

    def test_step_size_rounds_down(self):
        # 100 / 7 = 14.2857... → step 0.001 → 14.285
        qty = calc_order_qty(Decimal("100"), Decimal("7"), "0.001")
        assert qty == Decimal("14.285")

    def test_zero_price_returns_zero(self):
        qty = calc_order_qty(Decimal("100"), Decimal("0"), "0.001")
        assert qty == Decimal("0")

    def test_large_amount(self):
        qty = calc_order_qty(Decimal("10000"), Decimal("50000"), "0.00001")
        assert qty == Decimal("0.20000")


# ── is_completed ───────────────────────────────────────────────────────────────


class TestIsCompleted:
    def test_none_total_orders_never_completes(self):
        assert is_completed(999999, None) is False

    def test_not_completed_when_below_target(self):
        assert is_completed(9, 10) is False

    def test_completed_when_equal(self):
        assert is_completed(10, 10) is True

    def test_completed_when_exceeds(self):
        assert is_completed(11, 10) is True

    def test_zero_count_not_completed(self):
        assert is_completed(0, 5) is False

    def test_zero_total_orders_immediately_done(self):
        # total_orders=0이면 즉시 완료
        assert is_completed(0, 0) is True
