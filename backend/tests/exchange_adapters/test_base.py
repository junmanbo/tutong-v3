"""CcxtExchangeAdapter 파싱 로직 단위 테스트.

DB 불필요 — 순수 파싱/변환 로직을 CCXT mock으로 테스트.
커버리지 목표: 80%+
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exchange_adapters.base import (
    BalanceItem,
    CcxtExchangeAdapter,
    OrderBook,
    OrderRequest,
    OrderResponse,
    PriceTick,
    TickerData,
)

UTC = timezone.utc


# ── 테스트용 Concrete 구현 ─────────────────────────────────────────────────────


class FakeAdapter(CcxtExchangeAdapter):
    """_build_exchange를 mock으로 대체한 테스트용 어댑터."""

    def __init__(self, mock_exchange: MagicMock) -> None:
        # super().__init__() 없이 직접 주입
        self._exchange = mock_exchange


def make_mock_exchange() -> MagicMock:
    """비동기 메서드를 갖는 CCXT Exchange mock."""
    ex = MagicMock()
    ex.fetch_balance = AsyncMock()
    ex.create_order = AsyncMock()
    ex.cancel_order = AsyncMock()
    ex.fetch_order = AsyncMock()
    ex.fetch_ticker = AsyncMock()
    ex.fetch_order_book = AsyncMock()
    ex.watch_ticker = AsyncMock()
    ex.watch_orders = AsyncMock()
    ex.close = AsyncMock()
    return ex


# ── _to_decimal ───────────────────────────────────────────────────────────────


class TestToDecimal:
    def test_float_via_str(self):
        assert CcxtExchangeAdapter._to_decimal(0.1) == Decimal("0.1")

    def test_none_returns_zero(self):
        assert CcxtExchangeAdapter._to_decimal(None) == Decimal("0")

    def test_integer(self):
        assert CcxtExchangeAdapter._to_decimal(100) == Decimal("100")

    def test_string(self):
        assert CcxtExchangeAdapter._to_decimal("67230.5") == Decimal("67230.5")

    def test_zero(self):
        assert CcxtExchangeAdapter._to_decimal(0) == Decimal("0")

    def test_large_price(self):
        result = CcxtExchangeAdapter._to_decimal(67230.123456789)
        assert isinstance(result, Decimal)


# ── _parse_order ──────────────────────────────────────────────────────────────


class TestParseOrder:
    def _make_adapter(self) -> FakeAdapter:
        return FakeAdapter(make_mock_exchange())

    def _raw_order(self, **overrides) -> dict:
        base: dict = {
            "id": "12345",
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "limit",
            "status": "closed",
            "amount": 0.01,
            "filled": 0.01,
            "average": 50000.0,
            "fee": {"cost": 0.001, "currency": "BNB"},
        }
        base.update(overrides)
        return base

    def test_basic_parse(self):
        adapter = self._make_adapter()
        raw = self._raw_order()
        result = adapter._parse_order(raw)

        assert isinstance(result, OrderResponse)
        assert result.exchange_order_id == "12345"
        assert result.symbol == "BTC/USDT"
        assert result.side == "buy"
        assert result.order_type == "limit"
        assert result.status == "closed"
        assert result.filled_qty == Decimal("0.01")
        assert result.avg_fill_price == Decimal("50000.0")
        assert result.fee == Decimal("0.001")
        assert result.fee_currency == "BNB"
        assert result.raw == raw

    def test_no_fee_info(self):
        """fee 필드가 None인 경우 기본값 반환."""
        adapter = self._make_adapter()
        raw = self._raw_order(fee=None)
        result = adapter._parse_order(raw)
        assert result.fee == Decimal("0")
        assert result.fee_currency == ""

    def test_missing_average(self):
        """average 없을 때 avg_fill_price = 0."""
        adapter = self._make_adapter()
        raw = self._raw_order()
        del raw["average"]
        result = adapter._parse_order(raw)
        assert result.avg_fill_price == Decimal("0")

    def test_integer_order_id(self):
        """id가 정수인 경우 str 변환."""
        adapter = self._make_adapter()
        raw = self._raw_order(id=99999)
        result = adapter._parse_order(raw)
        assert result.exchange_order_id == "99999"

    def test_sell_order(self):
        adapter = self._make_adapter()
        raw = self._raw_order(side="sell", status="open", filled=0.0)
        result = adapter._parse_order(raw)
        assert result.side == "sell"
        assert result.status == "open"
        assert result.filled_qty == Decimal("0")


# ── get_balance ───────────────────────────────────────────────────────────────


class TestGetBalance:
    @pytest.mark.asyncio
    async def test_returns_nonzero_balances(self):
        mock_ex = make_mock_exchange()
        mock_ex.fetch_balance.return_value = {
            "total": {"BTC": 0.5, "ETH": 2.0, "USDT": 0.0},
            "free": {"BTC": 0.3, "ETH": 1.5, "USDT": 0.0},
            "used": {"BTC": 0.2, "ETH": 0.5, "USDT": 0.0},
        }
        adapter = FakeAdapter(mock_ex)
        result = await adapter.get_balance()

        assert len(result) == 2  # USDT(0) 제외
        assets = {b.asset for b in result}
        assert "BTC" in assets
        assert "ETH" in assets

    @pytest.mark.asyncio
    async def test_balance_values_are_decimal(self):
        mock_ex = make_mock_exchange()
        mock_ex.fetch_balance.return_value = {
            "total": {"BTC": 1.23456789},
            "free": {"BTC": 1.23456789},
            "used": {"BTC": 0.0},
        }
        adapter = FakeAdapter(mock_ex)
        result = await adapter.get_balance()

        assert len(result) == 1
        assert isinstance(result[0].free, Decimal)
        assert result[0].free == Decimal("1.23456789")

    @pytest.mark.asyncio
    async def test_empty_balance(self):
        mock_ex = make_mock_exchange()
        mock_ex.fetch_balance.return_value = {
            "total": {},
            "free": {},
            "used": {},
        }
        adapter = FakeAdapter(mock_ex)
        result = await adapter.get_balance()
        assert result == []


# ── get_ticker ────────────────────────────────────────────────────────────────


class TestGetTicker:
    @pytest.mark.asyncio
    async def test_ticker_parsing(self):
        ts_ms = 1700000000000
        mock_ex = make_mock_exchange()
        mock_ex.fetch_ticker.return_value = {
            "last": 67230.5,
            "bid": 67200.0,
            "ask": 67250.0,
            "timestamp": ts_ms,
        }
        adapter = FakeAdapter(mock_ex)
        result = await adapter.get_ticker("BTC/USDT")

        assert isinstance(result, TickerData)
        assert result.symbol == "BTC/USDT"
        assert result.price == Decimal("67230.5")
        assert result.bid == Decimal("67200.0")
        assert result.ask == Decimal("67250.0")
        expected_dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
        assert result.timestamp == expected_dt

    @pytest.mark.asyncio
    async def test_ticker_calls_exchange_with_correct_symbol(self):
        mock_ex = make_mock_exchange()
        mock_ex.fetch_ticker.return_value = {
            "last": 100.0,
            "bid": 99.0,
            "ask": 101.0,
            "timestamp": 1700000000000,
        }
        adapter = FakeAdapter(mock_ex)
        await adapter.get_ticker("ETH/USDT")
        mock_ex.fetch_ticker.assert_called_once_with("ETH/USDT")


# ── get_orderbook ─────────────────────────────────────────────────────────────


class TestGetOrderBook:
    @pytest.mark.asyncio
    async def test_orderbook_parsing(self):
        mock_ex = make_mock_exchange()
        mock_ex.fetch_order_book.return_value = {
            "bids": [[67000.0, 0.5], [66900.0, 1.0]],
            "asks": [[67100.0, 0.3], [67200.0, 0.7]],
        }
        adapter = FakeAdapter(mock_ex)
        result = await adapter.get_orderbook("BTC/USDT")

        assert isinstance(result, OrderBook)
        assert len(result.bids) == 2
        assert len(result.asks) == 2
        assert result.bids[0][0] == Decimal("67000.0")
        assert result.bids[0][1] == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_orderbook_default_depth(self):
        mock_ex = make_mock_exchange()
        mock_ex.fetch_order_book.return_value = {"bids": [], "asks": []}
        adapter = FakeAdapter(mock_ex)
        await adapter.get_orderbook("BTC/USDT")
        mock_ex.fetch_order_book.assert_called_once_with("BTC/USDT", limit=20)

    @pytest.mark.asyncio
    async def test_orderbook_custom_depth(self):
        mock_ex = make_mock_exchange()
        mock_ex.fetch_order_book.return_value = {"bids": [], "asks": []}
        adapter = FakeAdapter(mock_ex)
        await adapter.get_orderbook("BTC/USDT", depth=5)
        mock_ex.fetch_order_book.assert_called_once_with("BTC/USDT", limit=5)


# ── place_order ───────────────────────────────────────────────────────────────


class TestPlaceOrder:
    @pytest.mark.asyncio
    async def test_limit_buy_order(self):
        mock_ex = make_mock_exchange()
        mock_ex.create_order.return_value = {
            "id": "ORD001",
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "limit",
            "status": "open",
            "amount": 0.01,
            "filled": 0.0,
            "average": None,
            "fee": {"cost": 0.0, "currency": "BNB"},
        }
        adapter = FakeAdapter(mock_ex)
        req = OrderRequest(
            symbol="BTC/USDT",
            side="buy",
            order_type="limit",
            qty=Decimal("0.01"),
            price=Decimal("50000"),
        )
        result = await adapter.place_order(req)

        assert isinstance(result, OrderResponse)
        assert result.exchange_order_id == "ORD001"
        mock_ex.create_order.assert_called_once_with(
            symbol="BTC/USDT",
            type="limit",
            side="buy",
            amount=0.01,
            price=50000.0,
            params={},
        )

    @pytest.mark.asyncio
    async def test_upbit_market_buy_uses_cost(self):
        """업비트 시장가 매수: qty 대신 cost(amount) 파라미터 사용."""
        mock_ex = make_mock_exchange()
        mock_ex.create_order.return_value = {
            "id": "ORD002",
            "symbol": "BTC/KRW",
            "side": "buy",
            "type": "market",
            "status": "closed",
            "amount": None,
            "filled": 0.001,
            "average": 67000000.0,
            "fee": {"cost": 100.0, "currency": "KRW"},
        }
        adapter = FakeAdapter(mock_ex)
        req = OrderRequest(
            symbol="BTC/KRW",
            side="buy",
            order_type="market",
            amount=Decimal("100000"),  # 금액 기준 매수
        )
        result = await adapter.place_order(req)

        call_kwargs = mock_ex.create_order.call_args.kwargs
        assert call_kwargs["params"]["cost"] == 100000.0
        assert call_kwargs["amount"] == 100000.0


# ── cancel_order ──────────────────────────────────────────────────────────────


class TestCancelOrder:
    @pytest.mark.asyncio
    async def test_cancel_returns_true(self):
        mock_ex = make_mock_exchange()
        mock_ex.cancel_order.return_value = {}
        adapter = FakeAdapter(mock_ex)
        result = await adapter.cancel_order("ORD001", "BTC/USDT")
        assert result is True
        mock_ex.cancel_order.assert_called_once_with("ORD001", "BTC/USDT")


# ── validate_credentials ──────────────────────────────────────────────────────


class TestValidateCredentials:
    @pytest.mark.asyncio
    async def test_valid_credentials(self):
        import ccxt.async_support as ccxt
        mock_ex = make_mock_exchange()
        mock_ex.fetch_balance.return_value = {"total": {}}
        adapter = FakeAdapter(mock_ex)
        result = await adapter.validate_credentials()
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_credentials(self):
        import ccxt.async_support as ccxt
        mock_ex = make_mock_exchange()
        mock_ex.fetch_balance.side_effect = ccxt.AuthenticationError("Invalid key")
        adapter = FakeAdapter(mock_ex)
        result = await adapter.validate_credentials()
        assert result is False
