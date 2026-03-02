"""Binance 거래소 어댑터 — CCXT async_support 기반."""
from __future__ import annotations

import asyncio
from decimal import Decimal

import ccxt.async_support as ccxt

from app.exchange_adapters.base import (
    BalanceItem,
    CcxtExchangeAdapter,
    PriceTick,
)


class BinanceAdapter(CcxtExchangeAdapter):
    """Binance Spot 어댑터."""

    def _build_exchange(self, config: dict) -> ccxt.binance:
        return ccxt.binance(
            {
                **config,
                "options": {
                    "defaultType": "spot",
                    "adjustForTimeDifference": True,  # 서버 시간 오차 자동 보정
                },
            }
        )

    async def get_balance(self) -> list[BalanceItem]:
        """Binance 잔고: raw['free'], raw['used'] 딕셔너리 구조."""
        raw = await self._exchange.fetch_balance()
        result = []
        for asset, total in raw["total"].items():
            if self._to_decimal(total) > Decimal("0"):
                result.append(
                    BalanceItem(
                        asset=asset,
                        free=self._to_decimal(raw["free"].get(asset, 0)),
                        locked=self._to_decimal(raw["used"].get(asset, 0)),
                    )
                )
        return result

    async def price_stream(self, symbol: str):
        """Binance miniTicker WebSocket — CCXT watch_ticker."""
        try:
            while True:
                try:
                    ticker = await self._exchange.watch_ticker(symbol)
                    yield PriceTick(
                        symbol=symbol,
                        price=self._to_decimal(ticker["last"]),
                        timestamp=__import__("datetime").datetime.fromtimestamp(
                            ticker["timestamp"] / 1000,
                            tz=__import__("datetime").timezone.utc,
                        ),
                    )
                except ccxt.NetworkError:
                    await asyncio.sleep(1)
        finally:
            await self._exchange.close()

    @classmethod
    def create_testnet(cls, api_key: str, secret: str) -> "BinanceAdapter":
        """Binance Testnet 인스턴스 생성 (https://testnet.binance.vision)."""
        adapter: BinanceAdapter = cls.__new__(cls)
        adapter._exchange = ccxt.binance(
            {
                "apiKey": api_key,
                "secret": secret,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "spot",
                    "adjustForTimeDifference": True,
                },
            }
        )
        adapter._exchange.set_sandbox_mode(True)
        return adapter
