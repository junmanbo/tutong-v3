"""거래소 어댑터 공통 인터페이스 및 데이터 모델.

모든 거래소 어댑터는 AbstractExchangeAdapter를 구현해야 합니다.
CCXT 기반 거래소(Binance·Upbit)는 CcxtExchangeAdapter를 상속합니다.
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator

import ccxt.async_support as ccxt
from pydantic import BaseModel

UTC = timezone.utc


# ── 공통 데이터 모델 ──────────────────────────────────────────────────────────


class BalanceItem(BaseModel):
    asset: str       # 예: "BTC", "KRW", "USDT", "005930"
    free: Decimal    # 사용 가능 잔고
    locked: Decimal  # 주문에 묶인 잔고


class OrderRequest(BaseModel):
    symbol: str
    side: str               # "buy" | "sell"
    order_type: str         # "limit" | "market"
    qty: Decimal | None = None
    amount: Decimal | None = None   # qty 또는 amount 중 하나 (업비트 시장가 매수)
    price: Decimal | None = None    # limit 주문 시 필수


class OrderResponse(BaseModel):
    exchange_order_id: str
    symbol: str
    side: str
    order_type: str
    status: str             # "open" | "closed" | "canceled" | "partially_filled"
    requested_qty: Decimal | None
    filled_qty: Decimal
    avg_fill_price: Decimal | None
    fee: Decimal
    fee_currency: str
    raw: dict               # 거래소 원본 응답


class TickerData(BaseModel):
    symbol: str
    price: Decimal
    bid: Decimal
    ask: Decimal
    timestamp: datetime


class PriceTick(BaseModel):
    symbol: str
    price: Decimal
    timestamp: datetime


class OrderBook(BaseModel):
    bids: list[list[Decimal]]  # [[price, qty], ...]
    asks: list[list[Decimal]]


# ── 추상 어댑터 ───────────────────────────────────────────────────────────────


class AbstractExchangeAdapter(ABC):
    """모든 거래소 어댑터가 구현해야 하는 인터페이스."""

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """API Key 유효성 검증. 계좌 연동 시 1회 호출."""
        ...

    @abstractmethod
    async def get_balance(self) -> list[BalanceItem]:
        """전체 잔고 조회."""
        ...

    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """주문 발행."""
        ...

    @abstractmethod
    async def cancel_order(self, exchange_order_id: str, symbol: str) -> bool:
        """주문 취소."""
        ...

    @abstractmethod
    async def get_order(self, exchange_order_id: str, symbol: str) -> OrderResponse:
        """단일 주문 조회."""
        ...

    @abstractmethod
    async def get_ticker(self, symbol: str) -> TickerData:
        """현재가 조회."""
        ...

    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """호가 조회."""
        ...

    @abstractmethod
    async def price_stream(self, symbol: str) -> AsyncGenerator[PriceTick, None]:
        """WebSocket 실시간 가격 스트림 (async generator)."""
        ...

    @abstractmethod
    async def order_update_stream(self) -> AsyncGenerator[OrderResponse, None]:
        """WebSocket 주문 체결 이벤트 스트림."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """리소스 정리 (aiohttp 세션 등)."""
        ...


# ── CCXT 공통 베이스 (Binance·Upbit 공유) ────────────────────────────────────


class CcxtExchangeAdapter(AbstractExchangeAdapter):
    """CCXT async_support 기반 거래소 어댑터 공통 베이스."""

    _exchange: ccxt.Exchange

    def __init__(self, api_key: str, secret: str, options: dict | None = None) -> None:
        config: dict = {
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "options": options or {},
        }
        self._exchange = self._build_exchange(config)

    def _build_exchange(self, config: dict) -> ccxt.Exchange:
        raise NotImplementedError

    async def close(self) -> None:
        await self._exchange.close()

    @staticmethod
    def _to_decimal(value: float | str | int | None) -> Decimal:
        """CCXT float → Decimal 안전 변환 (str 경유 필수)."""
        if value is None:
            return Decimal("0")
        return Decimal(str(value))

    async def _validate_order_request(self, order: OrderRequest) -> None:
        """거래소별 주문 전 검증 훅."""
        return None

    # ── 공통 구현 ─────────────────────────────────────────────────────────────

    async def validate_credentials(self) -> bool:
        try:
            await self._exchange.fetch_balance()
            return True
        except ccxt.AuthenticationError:
            return False
        finally:
            await self.close()

    async def get_balance(self) -> list[BalanceItem]:
        raw = await self._exchange.fetch_balance()
        result = []
        for asset, total in raw["total"].items():
            if self._to_decimal(total) > Decimal("0"):
                result.append(
                    BalanceItem(
                        asset=asset,
                        free=self._to_decimal(raw["free"].get(asset)),
                        locked=self._to_decimal(raw["used"].get(asset)),
                    )
                )
        return result

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        await self._validate_order_request(order)

        params: dict = {}
        amount = float(order.qty) if order.qty is not None else None
        price = float(order.price) if order.price is not None else None

        # 업비트 시장가 매수: cost 기준
        if order.amount is not None and order.order_type == "market" and order.side == "buy":
            cost = float(order.amount)
            params["cost"] = cost
            # 일부 거래소(예: Upbit)는 market buy에서 amount를 cost로 전달해야 함
            amount = cost

        raw = await self._exchange.create_order(
            symbol=order.symbol,
            type=order.order_type,
            side=order.side,
            amount=amount,
            price=price,
            params=params,
        )
        return self._parse_order(raw)

    async def cancel_order(self, exchange_order_id: str, symbol: str) -> bool:
        await self._exchange.cancel_order(exchange_order_id, symbol)
        return True

    async def get_order(self, exchange_order_id: str, symbol: str) -> OrderResponse:
        raw = await self._exchange.fetch_order(exchange_order_id, symbol)
        return self._parse_order(raw)

    async def get_ticker(self, symbol: str) -> TickerData:
        raw = await self._exchange.fetch_ticker(symbol)
        return TickerData(
            symbol=symbol,
            price=self._to_decimal(raw["last"]),
            bid=self._to_decimal(raw["bid"]),
            ask=self._to_decimal(raw["ask"]),
            timestamp=datetime.fromtimestamp(raw["timestamp"] / 1000, tz=UTC),
        )

    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        raw = await self._exchange.fetch_order_book(symbol, limit=depth)
        return OrderBook(
            bids=[[self._to_decimal(p), self._to_decimal(q)] for p, q in raw["bids"]],
            asks=[[self._to_decimal(p), self._to_decimal(q)] for p, q in raw["asks"]],
        )

    def _parse_order(self, raw: dict) -> OrderResponse:
        """CCXT 통합 주문 응답 → OrderResponse 변환."""
        fee_info = raw.get("fee") or {}
        return OrderResponse(
            exchange_order_id=str(raw["id"]),
            symbol=raw["symbol"],
            side=raw["side"],
            order_type=raw["type"],
            status=raw["status"],
            requested_qty=self._to_decimal(raw.get("amount")),
            filled_qty=self._to_decimal(raw.get("filled")),
            avg_fill_price=self._to_decimal(raw.get("average")),
            fee=self._to_decimal(fee_info.get("cost")),
            fee_currency=fee_info.get("currency", ""),
            raw=raw,
        )

    async def price_stream(self, symbol: str) -> AsyncGenerator[PriceTick, None]:
        """CCXT watch_ticker 기반 WebSocket 가격 스트림."""
        try:
            while True:
                try:
                    ticker = await self._exchange.watch_ticker(symbol)
                    yield PriceTick(
                        symbol=symbol,
                        price=self._to_decimal(ticker["last"]),
                        timestamp=datetime.fromtimestamp(
                            ticker["timestamp"] / 1000, tz=UTC
                        ),
                    )
                except ccxt.NetworkError:
                    await asyncio.sleep(1)
        finally:
            await self._exchange.close()

    async def order_update_stream(self) -> AsyncGenerator[OrderResponse, None]:
        """CCXT watch_orders 기반 WebSocket 주문 체결 스트림."""
        try:
            while True:
                try:
                    orders = await self._exchange.watch_orders()
                    for raw in orders:
                        yield self._parse_order(raw)
                except ccxt.NetworkError:
                    await asyncio.sleep(1)
        finally:
            await self._exchange.close()
