from __future__ import annotations

import asyncio

import pytest

from app.exchange_adapters.binance import BinanceAdapter
from app.exchange_adapters.factory import get_adapter
from app.exchange_adapters.kis import KisAdapter
from app.exchange_adapters.kiwoom import KiwoomAdapter
from app.exchange_adapters.upbit import UpbitAdapter
from app.models import ExchangeTypeEnum


def test_factory_returns_binance_adapter() -> None:
    adapter = get_adapter(
        ExchangeTypeEnum.binance,
        api_key="k",
        api_secret="s",
    )
    assert isinstance(adapter, BinanceAdapter)


def test_factory_returns_upbit_adapter() -> None:
    adapter = get_adapter(
        ExchangeTypeEnum.upbit,
        api_key="k",
        api_secret="s",
    )
    assert isinstance(adapter, UpbitAdapter)


def test_factory_returns_kis_adapter_with_extra_params() -> None:
    adapter = get_adapter(
        ExchangeTypeEnum.kis,
        api_key="app-key",
        api_secret="app-secret",
        extra_params={
            "CANO": "12345678",
            "ACNT_PRDT_CD": "01",
            "is_mock": True,
        },
    )
    assert isinstance(adapter, KisAdapter)
    assert adapter._cano == "12345678"
    assert adapter._acnt_prdt_cd == "01"
    assert adapter._is_mock is True
    asyncio.run(adapter.close())


def test_factory_returns_kiwoom_adapter_with_extra_params() -> None:
    adapter = get_adapter(
        ExchangeTypeEnum.kiwoom,
        api_key="app-key",
        api_secret="secret-key",
        extra_params={
            "account_no": "11112222",
            "is_mock": True,
        },
    )
    assert isinstance(adapter, KiwoomAdapter)
    assert adapter._account_no == "11112222"
    assert adapter._is_mock is True
    asyncio.run(adapter.close())


def test_factory_raises_for_unsupported_exchange() -> None:
    with pytest.raises(ValueError):
        get_adapter("unknown", api_key="k", api_secret="s")  # type: ignore[arg-type]
