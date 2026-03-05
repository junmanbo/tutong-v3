from __future__ import annotations

from unittest.mock import patch

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
