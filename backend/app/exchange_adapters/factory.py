"""거래소 어댑터 팩토리.

ExchangeAccount 모델의 exchange 타입에 따라 적절한 어댑터 인스턴스를 반환합니다.
API Key/Secret는 호출 시 복호화된 평문으로 전달합니다.
"""
from __future__ import annotations

import json

from app.exchange_adapters.base import AbstractExchangeAdapter
from app.exchange_adapters.binance import BinanceAdapter
from app.exchange_adapters.kis import KisAdapter
from app.exchange_adapters.kiwoom import KiwoomAdapter
from app.exchange_adapters.upbit import UpbitAdapter
from app.models import ExchangeTypeEnum


def get_adapter(
    exchange: ExchangeTypeEnum,
    api_key: str,
    api_secret: str,
    extra_params: dict | None = None,
) -> AbstractExchangeAdapter:
    """거래소 타입에 따라 어댑터 인스턴스 반환.

    Args:
        exchange: 거래소 타입 (ExchangeTypeEnum)
        api_key: 복호화된 API Key 평문
        api_secret: 복호화된 API Secret 평문
        extra_params: 추가 파라미터 (KIS: CANO/ACNT_PRDT_CD, Kiwoom: account_no 등)
    """
    params = extra_params or {}

    match exchange:
        case ExchangeTypeEnum.binance:
            return BinanceAdapter(api_key=api_key, secret=api_secret)

        case ExchangeTypeEnum.upbit:
            return UpbitAdapter(api_key=api_key, secret=api_secret)

        case ExchangeTypeEnum.kis:
            return KisAdapter(
                app_key=api_key,
                app_secret=api_secret,
                cano=params.get("CANO", ""),
                acnt_prdt_cd=params.get("ACNT_PRDT_CD", "01"),
                is_mock=params.get("is_mock", False),
            )

        case ExchangeTypeEnum.kiwoom:
            return KiwoomAdapter(
                app_key=api_key,
                secret_key=api_secret,
                account_no=params.get("account_no", ""),
                is_mock=params.get("is_mock", False),
            )

        case _:
            raise ValueError(f"Unsupported exchange: {exchange}")
