"""Spot Grid 전략 테스트."""
from decimal import Decimal

import pytest

from bot_engine.strategies.spot_grid import (
    GridConfig,
    GridLevel,
    build_grid,
    calc_grid_profit,
    get_buy_prices,
    on_buy_filled,
    on_sell_filled,
)


# ── GridConfig.from_dict ───────────────────────────────────────────────────────


class TestGridConfigFromDict:
    def test_defaults(self):
        cfg = GridConfig.from_dict("BTC/USDT", {})
        assert cfg.symbol == "BTC/USDT"
        assert cfg.upper == Decimal("0")
        assert cfg.lower == Decimal("0")
        assert cfg.grid_count == 10
        assert cfg.amount_per_grid == Decimal("100")
        assert cfg.arithmetic is True
        assert cfg.step_size == "0.00001"
        assert cfg.tick_size == "0.01"

    def test_custom_values(self):
        cfg = GridConfig.from_dict(
            "ETH/USDT",
            {
                "upper": "3000",
                "lower": "2000",
                "grid_count": 5,
                "amount_per_grid": "200",
                "arithmetic": False,
                "step_size": "0.001",
                "tick_size": "0.1",
            },
        )
        assert cfg.upper == Decimal("3000")
        assert cfg.lower == Decimal("2000")
        assert cfg.grid_count == 5
        assert cfg.amount_per_grid == Decimal("200")
        assert cfg.arithmetic is False


# ── build_grid ─────────────────────────────────────────────────────────────────


class TestBuildGrid:
    def _make_config(self, upper="50000", lower="40000", count=4,
                     amount="100", step_size="0.00001", tick_size="1"):
        return GridConfig(
            symbol="BTC/USDT",
            upper=Decimal(upper),
            lower=Decimal(lower),
            grid_count=count,
            amount_per_grid=Decimal(amount),
            arithmetic=True,
            step_size=step_size,
            tick_size=tick_size,
        )

    def test_level_count_excludes_upper(self):
        cfg = self._make_config(count=4)
        levels = build_grid(cfg)
        # 4개 구간 → 5개 가격 → 상한가 제외 → 4개 레벨
        assert len(levels) == 4

    def test_all_levels_are_buy(self):
        cfg = self._make_config(count=4)
        levels = build_grid(cfg)
        assert all(lv.side == "buy" for lv in levels)

    def test_all_order_ids_none(self):
        cfg = self._make_config(count=4)
        levels = build_grid(cfg)
        assert all(lv.order_id is None for lv in levels)

    def test_all_filled_false(self):
        cfg = self._make_config(count=4)
        levels = build_grid(cfg)
        assert all(lv.filled is False for lv in levels)

    def test_prices_ascending(self):
        cfg = self._make_config(count=4)
        levels = build_grid(cfg)
        prices = [lv.price for lv in levels]
        assert prices == sorted(prices)

    def test_arithmetic_equal_spacing(self):
        cfg = self._make_config(upper="50000", lower="40000", count=4, tick_size="1")
        levels = build_grid(cfg)
        prices = [lv.price for lv in levels]
        # 등간격: 40000, 42500, 45000, 47500 (50000 제외)
        assert prices[0] == Decimal("40000")
        assert prices[1] == Decimal("42500")
        assert prices[2] == Decimal("45000")
        assert prices[3] == Decimal("47500")

    def test_qty_positive_for_all_levels(self):
        cfg = self._make_config(count=4)
        levels = build_grid(cfg)
        assert all(lv.qty > Decimal("0") for lv in levels)

    def test_geometric_grid(self):
        cfg = GridConfig(
            symbol="BTC/USDT",
            upper=Decimal("10000"),
            lower=Decimal("1000"),
            grid_count=2,
            amount_per_grid=Decimal("100"),
            arithmetic=False,
            step_size="0.00001",
            tick_size="1",
        )
        levels = build_grid(cfg)
        # 등비: lower=1000, ratio=(10000/1000)^(1/2)=√10≈3.162
        # 가격: 1000, ~3162 (2개 레벨, 10000 제외)
        assert len(levels) == 2
        assert levels[0].price < levels[1].price


# ── get_buy_prices ─────────────────────────────────────────────────────────────


class TestGetBuyPrices:
    def test_returns_sorted_unique_buy_prices(self):
        levels = [
            GridLevel(price=Decimal("100"), qty=Decimal("1"), side="buy"),
            GridLevel(price=Decimal("200"), qty=Decimal("1"), side="sell"),
            GridLevel(price=Decimal("100"), qty=Decimal("1"), side="buy"),  # 중복
            GridLevel(price=Decimal("300"), qty=Decimal("1"), side="buy"),
        ]
        prices = get_buy_prices(levels)
        assert prices == [Decimal("100"), Decimal("300")]

    def test_empty_list(self):
        assert get_buy_prices([]) == []

    def test_only_sell_levels(self):
        levels = [GridLevel(price=Decimal("100"), qty=Decimal("1"), side="sell")]
        assert get_buy_prices(levels) == []


# ── on_buy_filled ──────────────────────────────────────────────────────────────


class TestOnBuyFilled:
    def _make_levels(self):
        return [
            GridLevel(price=Decimal("40000"), qty=Decimal("0.01"), side="buy"),
            GridLevel(price=Decimal("42500"), qty=Decimal("0.01"), side="buy"),
            GridLevel(price=Decimal("45000"), qty=Decimal("0.01"), side="buy"),
            GridLevel(price=Decimal("47500"), qty=Decimal("0.01"), side="buy"),
        ]

    def test_marks_level_as_filled(self):
        levels = self._make_levels()
        on_buy_filled(levels[0], levels)
        assert levels[0].filled is True

    def test_creates_sell_at_next_level(self):
        levels = self._make_levels()
        sell = on_buy_filled(levels[0], levels)
        assert sell is not None
        assert sell.side == "sell"
        assert sell.price == Decimal("42500")
        assert sell.qty == Decimal("0.01")

    def test_sell_level_added_to_list(self):
        levels = self._make_levels()
        original_count = len(levels)
        on_buy_filled(levels[0], levels)
        assert len(levels) == original_count + 1

    def test_top_level_returns_none(self):
        levels = self._make_levels()
        sell = on_buy_filled(levels[-1], levels)
        assert sell is None

    def test_top_level_still_marked_filled(self):
        levels = self._make_levels()
        on_buy_filled(levels[-1], levels)
        assert levels[-1].filled is True

    def test_middle_level_creates_correct_sell(self):
        levels = self._make_levels()
        sell = on_buy_filled(levels[1], levels)  # 42500 체결
        assert sell.price == Decimal("45000")

    def test_price_not_in_levels_returns_none(self):
        levels = self._make_levels()
        orphan = GridLevel(price=Decimal("99999"), qty=Decimal("0.01"), side="buy")
        result = on_buy_filled(orphan, levels)
        assert result is None

    def test_sell_level_preserves_qty(self):
        levels = self._make_levels()
        levels[0].qty = Decimal("0.05")
        sell = on_buy_filled(levels[0], levels)
        assert sell.qty == Decimal("0.05")


# ── on_sell_filled ─────────────────────────────────────────────────────────────


class TestOnSellFilled:
    def _make_levels_with_sell(self):
        # 실제 그리드 상태: on_buy_filled(42500)이 실행된 후 sell@45000 추가됨.
        # buy@45000은 여전히 levels에 남아 있어 get_buy_prices()에 포함됨.
        sell = GridLevel(price=Decimal("45000"), qty=Decimal("0.01"), side="sell")
        return [
            GridLevel(price=Decimal("40000"), qty=Decimal("0.01"), side="buy"),
            GridLevel(price=Decimal("42500"), qty=Decimal("0.01"), side="buy"),
            GridLevel(price=Decimal("45000"), qty=Decimal("0.01"), side="buy"),
            GridLevel(price=Decimal("47500"), qty=Decimal("0.01"), side="buy"),
            sell,
        ], sell

    def test_marks_level_as_filled(self):
        levels, sell = self._make_levels_with_sell()
        on_sell_filled(sell, levels)
        assert sell.filled is True

    def test_creates_buy_at_previous_level(self):
        levels, sell = self._make_levels_with_sell()
        buy = on_sell_filled(sell, levels)  # 45000 매도 체결
        assert buy is not None
        assert buy.side == "buy"
        assert buy.price == Decimal("42500")

    def test_buy_level_added_to_list(self):
        levels, sell = self._make_levels_with_sell()
        original_count = len(levels)
        on_sell_filled(sell, levels)
        assert len(levels) == original_count + 1

    def test_bottom_sell_level_returns_none(self):
        """매도 레벨이 최하단(아래에 매수 레벨 없음) → None."""
        sell = GridLevel(price=Decimal("40000"), qty=Decimal("0.01"), side="sell")
        levels = [
            GridLevel(price=Decimal("40000"), qty=Decimal("0.01"), side="buy"),
            sell,
        ]
        result = on_sell_filled(sell, levels)
        assert result is None

    def test_price_not_in_buy_levels_returns_none(self):
        levels = [
            GridLevel(price=Decimal("40000"), qty=Decimal("0.01"), side="buy"),
        ]
        orphan = GridLevel(price=Decimal("99999"), qty=Decimal("0.01"), side="sell")
        result = on_sell_filled(orphan, levels)
        assert result is None

    def test_buy_level_preserves_qty(self):
        levels, sell = self._make_levels_with_sell()
        sell.qty = Decimal("0.03")
        buy = on_sell_filled(sell, levels)
        assert buy.qty == Decimal("0.03")


# ── calc_grid_profit ───────────────────────────────────────────────────────────


class TestCalcGridProfit:
    def test_basic_profit(self):
        profit = calc_grid_profit(
            buy_price=Decimal("40000"),
            sell_price=Decimal("42500"),
            qty=Decimal("0.01"),
        )
        assert profit == Decimal("25")  # 2500 * 0.01

    def test_zero_profit_same_price(self):
        profit = calc_grid_profit(
            buy_price=Decimal("40000"),
            sell_price=Decimal("40000"),
            qty=Decimal("0.01"),
        )
        assert profit == Decimal("0")

    def test_loss_if_sell_below_buy(self):
        profit = calc_grid_profit(
            buy_price=Decimal("42500"),
            sell_price=Decimal("40000"),
            qty=Decimal("0.01"),
        )
        assert profit == Decimal("-25")

    def test_decimal_precision(self):
        profit = calc_grid_profit(
            buy_price=Decimal("0.001"),
            sell_price=Decimal("0.002"),
            qty=Decimal("1000"),
        )
        assert profit == Decimal("1")
