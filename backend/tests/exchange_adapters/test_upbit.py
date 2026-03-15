from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.exchange_adapters.base import OrderRequest
from app.exchange_adapters.upbit import UpbitAdapter


def test_upbit_build_exchange_uses_spot_default_type() -> None:
    with patch("app.exchange_adapters.upbit.ccxt.upbit") as mock_upbit:
        UpbitAdapter(api_key="k", secret="s")

    assert mock_upbit.call_count == 1
    config = mock_upbit.call_args.args[0]
    assert config["apiKey"] == "k"
    assert config["secret"] == "s"
    assert config["enableRateLimit"] is True
    assert config["options"]["defaultType"] == "spot"
    assert config["options"]["createMarketBuyOrderRequiresPrice"] is False


def test_upbit_rejects_limit_order_below_min_krw() -> None:
    with patch("app.exchange_adapters.upbit.ccxt.upbit"):
        adapter = UpbitAdapter(api_key="k", secret="s")

    try:
        asyncio.run(
            adapter._validate_order_request(
                OrderRequest(
                    symbol="XRP/KRW",
                    side="buy",
                    order_type="limit",
                    qty=Decimal("1"),
                    price=Decimal("4999"),
                )
            )
        )
    except ValueError as exc:
        assert "at least 5000 KRW" in str(exc)
    else:
        raise AssertionError("Expected ValueError for order below Upbit minimum")


def test_upbit_rejects_market_sell_below_min_krw() -> None:
    with patch("app.exchange_adapters.upbit.ccxt.upbit"):
        adapter = UpbitAdapter(api_key="k", secret="s")

    adapter.get_ticker = AsyncMock(  # type: ignore[method-assign]
        return_value=type(
            "Ticker",
            (),
            {
                "bid": Decimal("4900"),
                "ask": Decimal("5000"),
                "price": Decimal("4950"),
            },
        )()
    )

    try:
        asyncio.run(
            adapter._validate_order_request(
                OrderRequest(
                    symbol="XRP/KRW",
                    side="sell",
                    order_type="market",
                    qty=Decimal("1"),
                )
            )
        )
    except ValueError as exc:
        assert "at least 5000 KRW" in str(exc)
    else:
        raise AssertionError("Expected ValueError for order below Upbit minimum")
