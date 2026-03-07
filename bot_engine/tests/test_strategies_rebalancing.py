"""Rebalancing 전략 테스트."""
from decimal import Decimal

import pytest

from bot_engine.strategies.rebalancing import (
    RebalanceOrder,
    RebalancingConfig,
    calc_rebalance_orders,
    calc_weights,
    needs_rebalance,
)


# ── RebalancingConfig.from_dict ────────────────────────────────────────────────


class TestRebalancingConfigFromDict:
    def test_defaults(self):
        cfg = RebalancingConfig.from_dict({})
        assert cfg.assets == {}
        assert cfg.threshold_pct == Decimal("5")
        assert cfg.interval_seconds == 3600
        assert cfg.quote == "KRW"

    def test_custom_assets(self):
        cfg = RebalancingConfig.from_dict(
            {
                "assets": {"BTC": "50", "ETH": "30", "KRW": "20"},
                "threshold_pct": "3",
                "interval_seconds": 7200,
                "quote": "KRW",
            }
        )
        assert cfg.assets["BTC"] == Decimal("50")
        assert cfg.assets["ETH"] == Decimal("30")
        assert cfg.assets["KRW"] == Decimal("20")
        assert cfg.threshold_pct == Decimal("3")
        assert cfg.interval_seconds == 7200

    def test_asset_values_are_decimal(self):
        cfg = RebalancingConfig.from_dict({"assets": {"BTC": "33.33"}})
        assert isinstance(cfg.assets["BTC"], Decimal)


# ── calc_weights ───────────────────────────────────────────────────────────────


class TestCalcWeights:
    def test_simple_two_asset(self):
        balances = {"BTC": Decimal("1"), "KRW": Decimal("50000")}
        prices = {"BTC": Decimal("50000")}
        weights = calc_weights(balances, prices, quote="KRW")
        # BTC: 50000, KRW: 50000 → 각 50%
        assert weights["BTC"] == Decimal("50")
        assert weights["KRW"] == Decimal("50")

    def test_three_asset_portfolio(self):
        balances = {
            "BTC": Decimal("1"),    # 50000 KRW
            "ETH": Decimal("10"),   # 30000 KRW
            "KRW": Decimal("20000"),
        }
        prices = {"BTC": Decimal("50000"), "ETH": Decimal("3000")}
        weights = calc_weights(balances, prices, quote="KRW")
        total = Decimal("100000")
        assert weights["BTC"] == Decimal("50000") / total * 100
        assert weights["ETH"] == Decimal("30000") / total * 100
        assert weights["KRW"] == Decimal("20000") / total * 100

    def test_weights_sum_to_100(self):
        balances = {"BTC": Decimal("1"), "ETH": Decimal("5"), "KRW": Decimal("10000")}
        prices = {"BTC": Decimal("40000"), "ETH": Decimal("2000")}
        weights = calc_weights(balances, prices)
        total = sum(weights.values())
        assert abs(total - Decimal("100")) < Decimal("0.0001")

    def test_zero_balance_returns_zero_weight(self):
        balances = {"BTC": Decimal("0"), "KRW": Decimal("10000")}
        prices = {"BTC": Decimal("50000")}
        weights = calc_weights(balances, prices)
        assert weights["BTC"] == Decimal("0")
        assert weights["KRW"] == Decimal("100")

    def test_all_zero_balances_returns_zeros(self):
        balances = {"BTC": Decimal("0"), "ETH": Decimal("0")}
        prices = {"BTC": Decimal("50000"), "ETH": Decimal("3000")}
        weights = calc_weights(balances, prices)
        assert weights["BTC"] == Decimal("0")
        assert weights["ETH"] == Decimal("0")

    def test_asset_without_price_counted_as_zero(self):
        """가격 정보 없는 자산은 0 가치로 처리."""
        balances = {"UNKNOWN": Decimal("100"), "KRW": Decimal("10000")}
        prices = {}
        weights = calc_weights(balances, prices)
        assert weights["UNKNOWN"] == Decimal("0")
        assert weights["KRW"] == Decimal("100")

    def test_quote_asset_not_needing_price(self):
        """quote 자산(KRW)은 가격 조회 없이 잔고 그대로 사용."""
        balances = {"KRW": Decimal("10000")}
        prices = {}
        weights = calc_weights(balances, prices, quote="KRW")
        assert weights["KRW"] == Decimal("100")


# ── needs_rebalance ────────────────────────────────────────────────────────────


class TestNeedsRebalance:
    def test_no_rebalance_when_within_threshold(self):
        current = {"BTC": Decimal("50"), "KRW": Decimal("50")}
        target = {"BTC": Decimal("50"), "KRW": Decimal("50")}
        assert needs_rebalance(current, target, Decimal("5")) is False

    def test_rebalance_when_exceeds_threshold(self):
        current = {"BTC": Decimal("44"), "KRW": Decimal("56")}
        target = {"BTC": Decimal("50"), "KRW": Decimal("50")}
        # BTC: |44 - 50| = 6 >= 5
        assert needs_rebalance(current, target, Decimal("5")) is True

    def test_no_rebalance_when_exactly_at_threshold_minus_one(self):
        current = {"BTC": Decimal("45.1"), "KRW": Decimal("54.9")}
        target = {"BTC": Decimal("50"), "KRW": Decimal("50")}
        # BTC: |45.1 - 50| = 4.9 < 5
        assert needs_rebalance(current, target, Decimal("5")) is False

    def test_rebalance_when_exactly_at_threshold(self):
        current = {"BTC": Decimal("45"), "KRW": Decimal("55")}
        target = {"BTC": Decimal("50"), "KRW": Decimal("50")}
        # BTC: |45 - 50| = 5 >= 5
        assert needs_rebalance(current, target, Decimal("5")) is True

    def test_rebalance_when_asset_missing_from_current(self):
        """현재 잔고에 없는 자산은 0%로 처리."""
        current = {"KRW": Decimal("100")}
        target = {"BTC": Decimal("50"), "KRW": Decimal("50")}
        # BTC: |0 - 50| = 50 >= 5
        assert needs_rebalance(current, target, Decimal("5")) is True

    def test_three_assets_only_one_deviates(self):
        current = {"BTC": Decimal("50"), "ETH": Decimal("25"), "KRW": Decimal("25")}
        target = {"BTC": Decimal("50"), "ETH": Decimal("30"), "KRW": Decimal("20")}
        # ETH: |25 - 30| = 5 >= 5
        assert needs_rebalance(current, target, Decimal("5")) is True

    def test_empty_target_no_rebalance(self):
        current = {"BTC": Decimal("100")}
        target = {}
        assert needs_rebalance(current, target, Decimal("5")) is False


# ── calc_rebalance_orders ──────────────────────────────────────────────────────


class TestCalcRebalanceOrders:
    def test_buy_order_when_underweight(self):
        current = {"BTC": Decimal("40"), "KRW": Decimal("60")}
        target = {"BTC": Decimal("50"), "KRW": Decimal("50")}
        orders = calc_rebalance_orders(current, target, Decimal("10000"))
        buy_orders = [o for o in orders if o.side == "buy"]
        assert len(buy_orders) == 1
        assert buy_orders[0].asset == "BTC"
        assert buy_orders[0].amount == Decimal("1000")  # 10% of 10000

    def test_sell_order_when_overweight(self):
        current = {"BTC": Decimal("60"), "KRW": Decimal("40")}
        target = {"BTC": Decimal("50"), "KRW": Decimal("50")}
        orders = calc_rebalance_orders(current, target, Decimal("10000"))
        sell_orders = [o for o in orders if o.side == "sell"]
        assert len(sell_orders) == 1
        assert sell_orders[0].asset == "BTC"
        assert sell_orders[0].amount == Decimal("1000")

    def test_quote_asset_excluded_from_orders(self):
        current = {"BTC": Decimal("50"), "KRW": Decimal("50")}
        target = {"BTC": Decimal("60"), "KRW": Decimal("40")}
        orders = calc_rebalance_orders(current, target, Decimal("10000"), quote="KRW")
        # KRW는 주문 대상 아님
        assert all(o.asset != "KRW" for o in orders)

    def test_sell_before_buy_ordering(self):
        """매도 주문이 매수 주문보다 앞에 위치해야 함."""
        current = {"BTC": Decimal("60"), "ETH": Decimal("20"), "KRW": Decimal("20")}
        target = {"BTC": Decimal("40"), "ETH": Decimal("40"), "KRW": Decimal("20")}
        orders = calc_rebalance_orders(current, target, Decimal("10000"))
        sides = [o.side for o in orders]
        # sell이 buy보다 앞에 와야 함
        if "sell" in sides and "buy" in sides:
            assert sides.index("sell") < sides.index("buy")

    def test_balanced_portfolio_no_orders(self):
        current = {"BTC": Decimal("50"), "KRW": Decimal("50")}
        target = {"BTC": Decimal("50"), "KRW": Decimal("50")}
        orders = calc_rebalance_orders(current, target, Decimal("10000"))
        # diff=0이므로 주문 없음
        assert orders == []

    def test_new_asset_generates_buy(self):
        """현재 보유 없는 목표 자산 → 매수 주문."""
        current = {"BTC": Decimal("0"), "KRW": Decimal("100")}
        target = {"BTC": Decimal("50"), "KRW": Decimal("50")}
        orders = calc_rebalance_orders(current, target, Decimal("10000"))
        buy_orders = [o for o in orders if o.side == "buy" and o.asset == "BTC"]
        assert len(buy_orders) == 1
        assert buy_orders[0].amount == Decimal("5000")

    def test_order_amounts_are_positive(self):
        current = {"BTC": Decimal("30"), "ETH": Decimal("70")}
        target = {"BTC": Decimal("50"), "ETH": Decimal("50")}
        orders = calc_rebalance_orders(current, target, Decimal("10000"))
        assert all(o.amount > Decimal("0") for o in orders)
