"""Upbit 거래소 어댑터 — CCXT async_support 기반.

심볼 형식: CCXT 표준 (BTC/KRW, ETH/KRW) — CCXT가 업비트 원본(KRW-BTC)으로 자동 변환.
업비트 시장가 매수: qty가 아닌 KRW 금액 기준 (OrderRequest.amount 사용).
"""
from __future__ import annotations

import ccxt.async_support as ccxt

from app.exchange_adapters.base import CcxtExchangeAdapter


class UpbitAdapter(CcxtExchangeAdapter):
    """Upbit 거래소 어댑터."""

    def _build_exchange(self, config: dict) -> ccxt.upbit:
        options = config.get("options") or {}
        return ccxt.upbit(
            {
                **config,
                "options": {
                    "defaultType": "spot",
                    # Market buy에서 amount를 수량이 아닌 quote cost로 해석
                    "createMarketBuyOrderRequiresPrice": False,
                    **options,
                },
            }
        )
