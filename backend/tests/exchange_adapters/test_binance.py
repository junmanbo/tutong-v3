from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.exchange_adapters.binance import BinanceAdapter


def test_binance_build_exchange_uses_spot_and_time_adjust() -> None:
    with patch("app.exchange_adapters.binance.ccxt.binance") as mock_binance:
        BinanceAdapter(api_key="k", secret="s")

    assert mock_binance.call_count == 1
    config = mock_binance.call_args.args[0]
    assert config["apiKey"] == "k"
    assert config["secret"] == "s"
    assert config["enableRateLimit"] is True
    assert config["options"]["defaultType"] == "spot"
    assert config["options"]["adjustForTimeDifference"] is True


def test_create_testnet_sets_sandbox_mode() -> None:
    mock_exchange = MagicMock()
    with patch("app.exchange_adapters.binance.ccxt.binance", return_value=mock_exchange):
        adapter = BinanceAdapter.create_testnet(api_key="k", secret="s")

    assert adapter._exchange is mock_exchange
    mock_exchange.set_sandbox_mode.assert_called_once_with(True)
