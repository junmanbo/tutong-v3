"""Upbit 거래소 어댑터 — CCXT async_support 기반.

심볼 형식: CCXT 표준 (BTC/KRW, ETH/KRW) — CCXT가 업비트 원본(KRW-BTC)으로 자동 변환.
업비트 시장가 매수: qty가 아닌 KRW 금액 기준 (OrderRequest.amount 사용).
"""
from __future__ import annotations

from decimal import Decimal

import ccxt.async_support as ccxt

from app.bot_validations import UPBIT_MIN_ORDER_KRW, get_quote_currency
from app.exchange_adapters.base import CcxtExchangeAdapter
from app.exchange_adapters.base import OrderRequest


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

    async def _validate_order_request(self, order: OrderRequest) -> None:
        quote_currency = get_quote_currency(order.symbol)
        if quote_currency != "KRW":
            return

        notional = await self._estimate_order_notional(order)
        if notional < UPBIT_MIN_ORDER_KRW:
            raise ValueError(
                "Upbit orders must be at least "
                f"{UPBIT_MIN_ORDER_KRW} KRW. "
                f"Computed order value: {notional.normalize()} KRW."
            )

    async def _estimate_order_notional(self, order: OrderRequest) -> Decimal:
        if order.order_type == "market" and order.side == "buy" and order.amount is not None:
            return order.amount

        if order.qty is None:
            return Decimal("0")

        if order.price is not None:
            return order.qty * order.price

        ticker = await self.get_ticker(order.symbol)
        reference_price = ticker.bid if order.side == "sell" else ticker.ask or ticker.price
        return order.qty * reference_price
