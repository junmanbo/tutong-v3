"""Position Snowball 전략 테스트."""
from decimal import Decimal

import pytest

from bot_engine.strategies.snowball import (
    BuyRecord,
    SnowballConfig,
    calc_avg_price,
    calc_buy_qty,
    calc_total_qty,
    should_add_buy,
    should_take_profit,
)


# ── SnowballConfig.from_dict ───────────────────────────────────────────────────


class TestSnowballConfigFromDict:
    def test_defaults(self):
        cfg = SnowballConfig.from_dict("BTC/USDT", {})
        assert cfg.symbol == "BTC/USDT"
        assert cfg.drop_pct == Decimal("5")
        assert cfg.amount_per_buy == Decimal("100")
        assert cfg.take_profit_pct == Decimal("3")
        assert cfg.max_buys == 5
        assert cfg.step_size == "0.00001"

    def test_custom_values(self):
        cfg = SnowballConfig.from_dict(
            "ETH/USDT",
            {
                "drop_pct": "10",
                "amount_per_buy": "500",
                "take_profit_pct": "5",
                "max_buys": 3,
                "step_size": "0.001",
            },
        )
        assert cfg.drop_pct == Decimal("10")
        assert cfg.amount_per_buy == Decimal("500")
        assert cfg.take_profit_pct == Decimal("5")
        assert cfg.max_buys == 3
        assert cfg.step_size == "0.001"


# ── should_add_buy ─────────────────────────────────────────────────────────────


class TestShouldAddBuy:
    def test_adds_buy_when_drop_sufficient(self):
        # 100000 → 94000: 6% 하락, 기준 5%
        assert should_add_buy(Decimal("94000"), Decimal("100000"), Decimal("5")) is True

    def test_no_buy_when_drop_insufficient(self):
        # 100000 → 96000: 4% 하락, 기준 5%
        assert should_add_buy(Decimal("96000"), Decimal("100000"), Decimal("5")) is False

    def test_buy_when_exactly_at_threshold(self):
        # 100000 → 95000: 정확히 5% 하락
        assert should_add_buy(Decimal("95000"), Decimal("100000"), Decimal("5")) is True

    def test_no_buy_when_price_rises(self):
        assert should_add_buy(Decimal("110000"), Decimal("100000"), Decimal("5")) is False

    def test_no_buy_when_last_buy_price_zero(self):
        assert should_add_buy(Decimal("95000"), Decimal("0"), Decimal("5")) is False

    def test_no_buy_when_last_buy_price_negative(self):
        assert should_add_buy(Decimal("95000"), Decimal("-100"), Decimal("5")) is False

    def test_large_drop(self):
        # 100% 하락 (가격 0)
        assert should_add_buy(Decimal("0"), Decimal("100000"), Decimal("5")) is True

    def test_decimal_precision(self):
        # 정밀한 소수점 비교: 4.999...% 하락 → 기준 5% → False
        assert should_add_buy(
            Decimal("95001"), Decimal("100000"), Decimal("5")
        ) is False


# ── should_take_profit ─────────────────────────────────────────────────────────


class TestShouldTakeProfit:
    def test_takes_profit_when_gain_sufficient(self):
        # 평균가 100000, 현재 104000: 4% 상승, 기준 3%
        assert should_take_profit(Decimal("104000"), Decimal("100000"), Decimal("3")) is True

    def test_no_profit_when_gain_insufficient(self):
        # 평균가 100000, 현재 102000: 2% 상승, 기준 3%
        assert should_take_profit(Decimal("102000"), Decimal("100000"), Decimal("3")) is False

    def test_profit_when_exactly_at_threshold(self):
        # 정확히 3% 상승
        assert should_take_profit(Decimal("103000"), Decimal("100000"), Decimal("3")) is True

    def test_no_profit_when_price_drops(self):
        assert should_take_profit(Decimal("90000"), Decimal("100000"), Decimal("3")) is False

    def test_no_profit_when_avg_price_zero(self):
        assert should_take_profit(Decimal("104000"), Decimal("0"), Decimal("3")) is False

    def test_no_profit_when_avg_price_negative(self):
        assert should_take_profit(Decimal("104000"), Decimal("-100"), Decimal("3")) is False

    def test_zero_threshold_always_profit(self):
        """임계값이 0이면 가격이 평균가 이상이면 항상 익절."""
        assert should_take_profit(Decimal("100001"), Decimal("100000"), Decimal("0")) is True

    def test_no_profit_at_breakeven_with_zero_threshold(self):
        assert should_take_profit(Decimal("100000"), Decimal("100000"), Decimal("0")) is True


# ── calc_avg_price ─────────────────────────────────────────────────────────────


class TestCalcAvgPrice:
    def test_empty_returns_zero(self):
        assert calc_avg_price([]) == Decimal("0")

    def test_single_buy(self):
        buys = [BuyRecord(price=Decimal("50000"), qty=Decimal("0.01"))]
        assert calc_avg_price(buys) == Decimal("50000")

    def test_equal_qty_simple_average(self):
        buys = [
            BuyRecord(price=Decimal("40000"), qty=Decimal("1")),
            BuyRecord(price=Decimal("60000"), qty=Decimal("1")),
        ]
        assert calc_avg_price(buys) == Decimal("50000")

    def test_weighted_average_favors_larger_qty(self):
        buys = [
            BuyRecord(price=Decimal("40000"), qty=Decimal("3")),  # 더 많이 매수
            BuyRecord(price=Decimal("60000"), qty=Decimal("1")),
        ]
        avg = calc_avg_price(buys)
        # (40000*3 + 60000*1) / 4 = 180000/4 = 45000
        assert avg == Decimal("45000")

    def test_three_buys(self):
        buys = [
            BuyRecord(price=Decimal("100000"), qty=Decimal("0.01")),
            BuyRecord(price=Decimal("95000"), qty=Decimal("0.01")),
            BuyRecord(price=Decimal("90000"), qty=Decimal("0.01")),
        ]
        avg = calc_avg_price(buys)
        # (100000 + 95000 + 90000) / 3 = 95000
        assert avg == Decimal("95000")

    def test_zero_qty_returns_zero(self):
        buys = [BuyRecord(price=Decimal("50000"), qty=Decimal("0"))]
        assert calc_avg_price(buys) == Decimal("0")


# ── calc_total_qty ─────────────────────────────────────────────────────────────


class TestCalcTotalQty:
    def test_empty_returns_zero(self):
        assert calc_total_qty([]) == Decimal("0")

    def test_single_record(self):
        buys = [BuyRecord(price=Decimal("50000"), qty=Decimal("0.01"))]
        assert calc_total_qty(buys) == Decimal("0.01")

    def test_multiple_records(self):
        buys = [
            BuyRecord(price=Decimal("50000"), qty=Decimal("0.01")),
            BuyRecord(price=Decimal("45000"), qty=Decimal("0.02")),
            BuyRecord(price=Decimal("40000"), qty=Decimal("0.03")),
        ]
        assert calc_total_qty(buys) == Decimal("0.06")


# ── calc_buy_qty ───────────────────────────────────────────────────────────────


class TestCalcBuyQty:
    def test_basic_qty(self):
        qty = calc_buy_qty(Decimal("100"), Decimal("50000"), "0.00001")
        assert qty == Decimal("0.00200")

    def test_step_size_truncates(self):
        # 100 / 3 = 33.333... → step 1 → 33
        qty = calc_buy_qty(Decimal("100"), Decimal("3"), "1")
        assert qty == Decimal("33")

    def test_zero_price_returns_zero(self):
        qty = calc_buy_qty(Decimal("100"), Decimal("0"), "0.00001")
        assert qty == Decimal("0")
