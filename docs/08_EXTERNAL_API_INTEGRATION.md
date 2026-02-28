# 외부 API 연동 명세서 (External API Integration Spec)

**프로젝트명:** AutoTrade Platform  
**문서 버전:** v1.0  
**작성일:** 2025년  
**작성자:** PM / 개발자

---

## 목차

1. [공통 어댑터 설계 원칙](#1-공통-어댑터-설계-원칙)
2. [Binance (바이낸스)](#2-binance-바이낸스)
3. [Upbit (업비트)](#3-upbit-업비트)
4. [한국투자증권 KIS](#4-한국투자증권-kis)
5. [키움증권 REST API](#5-키움증권-rest-api)
6. [거래소 공통 데이터 정규화](#6-거래소-공통-데이터-정규화)
7. [Rate Limit 관리 전략](#7-rate-limit-관리-전략)
8. [변경 이력](#8-변경-이력)

---

## 1. 공통 어댑터 설계 원칙

### 1.0 거래소별 구현 방식

| 거래소 | 방식 | 라이브러리 | 비고 |
|--------|------|-----------|------|
| **Binance** | CCXT | `ccxt.async_support.binance` | REST + WebSocket(`watch_*`) 모두 CCXT |
| **Upbit** | CCXT | `ccxt.async_support.upbit` | REST + WebSocket(`watch_*`) 모두 CCXT |
| **한국투자증권** | 직접 구현 | `httpx` | CCXT 미지원, OAuth 2.0 + tr_id 구조 |
| **키움증권** | 직접 구현 | `httpx` | CCXT 미지원, App Key/Secret 구조 |

**CCXT 라이브러리 소개:**

> CCXT(CryptoCurrency eXchange Trading Library)는 100개 이상 거래소의 API를 단일 인터페이스로 통합하는 오픈소스 라이브러리입니다.
> Binance·Upbit 모두 공식 지원하며, REST API와 WebSocket 스트리밍을 동일한 메서드 시그니처로 사용할 수 있습니다.
> GitHub: https://github.com/ccxt/ccxt

**CCXT 설치:**

```bash
# backend/pyproject.toml 및 bot_engine/pyproject.toml에 추가
cd backend && uv add ccxt

# 성능 최적화 옵션 (선택)
# orjson: JSON 파싱 속도 개선 (ccxt가 자동 감지·사용)
uv add orjson
# coincurve: Binance ECDSA 서명 속도 개선 (45ms → 0.05ms)
uv add coincurve
```

**ccxt async 임포트 방법:**

```python
# ✅ async/await 기반 (bot_engine에서 사용 — WebSocket 포함)
import ccxt.async_support as ccxt

exchange = ccxt.binance({...})
await exchange.fetch_balance()         # REST 호출
await exchange.watch_ticker("BTC/USDT")  # WebSocket 스트리밍

# ✅ 동기 방식 (backend API 서버에서 간단 조회 시 사용 가능)
import ccxt
exchange = ccxt.binance({...})
exchange.fetch_balance()

# ❌ 금지 — ccxt.pro 별도 임포트 (ccxt v4부터 ccxt.async_support에 통합됨)
import ccxt.pro   # ModuleNotFoundError 발생
```

> **ccxt v4 이후 변경사항:** ccxt Pro(WebSocket)가 `ccxt.async_support`에 완전 통합되었습니다.
> `watch_*` 메서드는 `ccxt.async_support.*` 인스턴스에서 직접 사용합니다.

### 1.1 AbstractExchangeAdapter 구현 체크리스트

모든 거래소 어댑터는 아래 메서드를 반드시 구현해야 합니다.
CCXT 기반(Binance·Upbit)은 `CcxtExchangeAdapter` 공통 베이스를 상속하고,
KIS·키움은 이 ABC를 직접 구현합니다.

```python
from abc import ABC, abstractmethod
from decimal import Decimal

class AbstractExchangeAdapter(ABC):

    # ── 인증 ──────────────────────────────────────────
    @abstractmethod
    async def validate_credentials(self) -> bool:
        """API Key 유효성 검증. 계좌 연동 시 1회 호출."""
        ...

    # ── 잔고 ──────────────────────────────────────────
    @abstractmethod
    async def get_balance(self) -> list[BalanceItem]:
        """전체 잔고 조회. 0 이상인 자산만 반환."""
        ...

    # ── 주문 ──────────────────────────────────────────
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

    # ── 시세 ──────────────────────────────────────────
    @abstractmethod
    async def get_ticker(self, symbol: str) -> TickerData:
        """현재가 조회."""
        ...

    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """호가 조회."""
        ...

    # ── 실시간 스트리밍 ────────────────────────────────
    @abstractmethod
    async def price_stream(self, symbol: str):
        """WebSocket 실시간 가격 스트림 (async generator)."""
        ...

    @abstractmethod
    async def order_update_stream(self):
        """WebSocket 주문 체결 이벤트 스트림 (User Data Stream)."""
        ...
```

### 1.1-A CCXT 기반 공통 베이스 클래스

Binance·Upbit는 이 클래스를 상속해 공통 CCXT 로직을 재사용합니다.

```python
import ccxt.async_support as ccxt
from decimal import Decimal

class CcxtExchangeAdapter(AbstractExchangeAdapter):
    """CCXT 기반 거래소 어댑터 공통 베이스 (Binance·Upbit 공유)"""

    _exchange: ccxt.Exchange

    def __init__(self, api_key: str, secret: str, options: dict | None = None):
        # ❌ 절대 금지: 생성자에서 평문 API Key를 멤버 변수에 저장
        # 복호화된 키는 ccxt 객체에만 전달하고 즉시 소멸
        config = {
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,  # CCXT 내장 Rate Limit 활성화 (필수)
            "options": options or {},
        }
        self._exchange = self._build_exchange(config)

    def _build_exchange(self, config: dict) -> ccxt.Exchange:
        raise NotImplementedError

    async def close(self) -> None:
        """사용 완료 후 반드시 호출하여 aiohttp 세션 정리."""
        await self._exchange.close()

    # ── 공통 유틸 ────────────────────────────────────
    @staticmethod
    def _to_decimal(value: float | str | None) -> Decimal:
        """CCXT float 반환값 → Decimal 안전 변환.
        Decimal(float) 직접 변환은 부동소수점 오류 발생 — 반드시 str 경유.
        """
        if value is None:
            return Decimal("0")
        return Decimal(str(value))

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
        return [
            BalanceItem(
                asset=asset,
                free=self._to_decimal(info.get("free")),
                locked=self._to_decimal(info.get("used")),
            )
            for asset, info in raw["total"].items()
            if self._to_decimal(info) > Decimal("0")
        ]

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        raw = await self._exchange.create_order(
            symbol=order.symbol,
            type=order.order_type,
            side=order.side,
            amount=float(order.qty) if order.qty else None,
            price=float(order.price) if order.price else None,
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
        """CCXT 통합 주문 응답 → 내부 OrderResponse 변환."""
        return OrderResponse(
            exchange_order_id=str(raw["id"]),
            symbol=raw["symbol"],
            side=raw["side"],
            order_type=raw["type"],
            status=raw["status"],
            requested_qty=self._to_decimal(raw.get("amount")),
            filled_qty=self._to_decimal(raw.get("filled")),
            avg_fill_price=self._to_decimal(raw.get("average")),
            fee=self._to_decimal(raw.get("fee", {}).get("cost")),
            fee_currency=raw.get("fee", {}).get("currency", ""),
            raw=raw,
        )

    async def price_stream(self, symbol: str):
        """WebSocket 실시간 가격 스트림 (CCXT watch_ticker — async generator)."""
        try:
            while True:
                ticker = await self._exchange.watch_ticker(symbol)
                yield PriceTick(
                    symbol=symbol,
                    price=self._to_decimal(ticker["last"]),
                    timestamp=datetime.fromtimestamp(ticker["timestamp"] / 1000, tz=UTC),
                )
        finally:
            await self._exchange.close()

    async def order_update_stream(self):
        """WebSocket 주문 체결 스트림 (CCXT watch_orders)."""
        try:
            while True:
                orders = await self._exchange.watch_orders()
                for raw in orders:
                    yield self._parse_order(raw)
        finally:
            await self._exchange.close()
```

### 1.2 공통 데이터 모델 (Pydantic)

```python
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime

class BalanceItem(BaseModel):
    asset: str          # 예: "BTC", "USDT", "KRW"
    free: Decimal       # 사용 가능 잔고
    locked: Decimal     # 주문에 묶인 잔고

class OrderRequest(BaseModel):
    symbol: str
    side: str           # "buy" | "sell"
    order_type: str     # "limit" | "market"
    qty: Decimal | None = None
    amount: Decimal | None = None   # qty 또는 amount 중 하나
    price: Decimal | None = None    # limit 주문 시 필수

class OrderResponse(BaseModel):
    exchange_order_id: str
    symbol: str
    side: str
    order_type: str
    status: str         # "open" | "filled" | "cancelled" | "partially_filled"
    requested_qty: Decimal | None
    filled_qty: Decimal
    avg_fill_price: Decimal | None
    fee: Decimal
    fee_currency: str
    raw: dict           # 거래소 원본 응답

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
```

---

## 2. Binance (바이낸스) — CCXT 기반

**공식 문서:** https://binance-docs.github.io/apidocs/spot/en/  
**CCXT 문서:** https://docs.ccxt.com/#/exchanges/binance  
**구현 방식:** `ccxt.async_support.binance` — REST + WebSocket 모두 CCXT 사용

### 2.1 어댑터 구현

```python
# bot_engine/exchange_adapters/binance.py  (또는 backend/app/exchange_adapters/binance.py)
import ccxt.async_support as ccxt
from .base import CcxtExchangeAdapter

class BinanceAdapter(CcxtExchangeAdapter):
    """Binance Spot 어댑터 — CCXT async_support 기반."""

    def _build_exchange(self, config: dict) -> ccxt.binance:
        return ccxt.binance({
            **config,
            "options": {
                "defaultType": "spot",            # spot | margin | future
                "adjustForTimeDifference": True,  # 서버 시간 오차 자동 보정
            },
        })

    async def get_balance(self) -> list[BalanceItem]:
        """Binance 잔고: raw['free'], raw['used'] 딕셔너리 구조."""
        raw = await self._exchange.fetch_balance()
        result = []
        for asset, total in raw["total"].items():
            if self._to_decimal(total) > Decimal("0"):
                result.append(BalanceItem(
                    asset=asset,
                    free=self._to_decimal(raw["free"].get(asset, 0)),
                    locked=self._to_decimal(raw["used"].get(asset, 0)),
                ))
        return result

    async def price_stream(self, symbol: str):
        """Binance miniTicker WebSocket — CCXT watch_ticker.
        CCXT 내부: wss://stream.binance.com:9443/ws/{symbol}@miniTicker
        """
        while True:
            try:
                ticker = await self._exchange.watch_ticker(symbol)
                yield PriceTick(
                    symbol=symbol,
                    price=self._to_decimal(ticker["last"]),
                    timestamp=datetime.fromtimestamp(ticker["timestamp"] / 1000, tz=UTC),
                )
            except ccxt.NetworkError:
                await asyncio.sleep(1)

    async def order_update_stream(self):
        """Binance User Data Stream — CCXT watch_orders.
        CCXT가 listenKey 발급·30분마다 자동 갱신을 처리합니다.
        """
        while True:
            try:
                orders = await self._exchange.watch_orders()
                for raw in orders:
                    yield self._parse_order(raw)
            except ccxt.NetworkError:
                await asyncio.sleep(1)

    # ── 테스트넷 팩토리 메서드 ─────────────────────────
    @classmethod
    def create_testnet(cls, api_key: str, secret: str) -> "BinanceAdapter":
        """Binance Testnet 인스턴스 생성.
        테스트넷 키: https://testnet.binance.vision
        """
        adapter = cls.__new__(cls)
        adapter._exchange = ccxt.binance({
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot", "adjustForTimeDifference": True},
        })
        adapter._exchange.set_sandbox_mode(True)  # Testnet URL 자동 적용
        return adapter
```

### 2.2 심볼 형식

| 내부 표준 (CCXT) | 거래소 전송값 |
|----------------|-------------|
| `BTC/USDT` | `BTCUSDT` |
| `ETH/USDT` | `ETHUSDT` |

> CCXT는 내부적으로 `BTC/USDT` → `BTCUSDT` 변환을 자동으로 처리합니다. 코드에서는 항상 슬래시 형식(`BTC/USDT`)을 사용하세요.

### 2.3 주요 CCXT 메서드 매핑

| 기능 | CCXT 메서드 | 내부 래퍼 |
|------|------------|---------|
| 잔고 조회 | `fetch_balance()` | `get_balance()` |
| 현재가 | `fetch_ticker(symbol)` | `get_ticker()` |
| 호가 | `fetch_order_book(symbol, limit)` | `get_orderbook()` |
| 지정가 주문 | `create_order(symbol, 'limit', side, amount, price)` | `place_order()` |
| 시장가 주문 | `create_order(symbol, 'market', side, amount)` | `place_order()` |
| 주문 취소 | `cancel_order(id, symbol)` | `cancel_order()` |
| 주문 조회 | `fetch_order(id, symbol)` | `get_order()` |
| 실시간 가격 | `watch_ticker(symbol)` | `price_stream()` |
| 주문 체결 이벤트 | `watch_orders()` | `order_update_stream()` |

### 2.4 Celery Task에서 CCXT async 사용 패턴

Celery Worker는 동기 환경입니다. `ccxt.async_support`(asyncio)를 Celery Task 내에서 사용하려면 전용 이벤트 루프를 스레드에서 실행해야 합니다.

```python
# bot_engine/workers/spot_grid.py
import asyncio
from celery import Task
from bot_engine.exchange_adapters.binance import BinanceAdapter
from bot_engine.utils.crypto import decrypt
from app.core.config import settings

class AsyncTask(Task):
    """asyncio 코루틴을 Celery Task에서 실행하기 위한 베이스 클래스."""
    _loop: asyncio.AbstractEventLoop | None = None

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        return self._loop

    def run_async(self, coro):
        return self.loop.run_until_complete(coro)


@celery_app.task(bind=True, base=AsyncTask)
def run_spot_grid_tick(self, bot_id: str, api_key_enc: str, secret_enc: str):
    """Spot Grid 봇 1 틱 실행 — Celery Task."""
    async def _run():
        adapter = BinanceAdapter(
            api_key=decrypt(api_key_enc, settings.ENCRYPTION_KEY),
            secret=decrypt(secret_enc, settings.ENCRYPTION_KEY),
        )
        try:
            ticker = await adapter.get_ticker("BTC/USDT")
            # ... 봇 로직
        finally:
            await adapter.close()  # aiohttp 세션 반드시 정리

    self.run_async(_run())
```

### 2.5 Rate Limit

CCXT `enableRateLimit: True` 설정 시 자동으로 Rate Limit을 준수합니다. 추가 애플리케이션 레벨 제어가 필요한 경우에만 아래 값을 참고하세요.

| 유형 | 한도 | CCXT 처리 |
|------|------|-----------|
| Request Weight | 1200 weight/min (IP) | 자동 대기 |
| Orders | 10 orders/sec, 100,000 orders/24h | 자동 대기 |
| Weight 초과 | HTTP 429 | `ccxt.RateLimitExceeded` 예외 |

### 2.6 예외 처리

```python
import ccxt

try:
    order = await adapter.place_order(order_req)
except ccxt.AuthenticationError:
    # API Key 만료 또는 잘못된 키
    ...
except ccxt.InsufficientFunds:
    # 잔고 부족
    ...
except ccxt.InvalidOrder:
    # Lot size, 최소 주문금액 위반
    ...
except ccxt.RateLimitExceeded:
    # enableRateLimit=True 임에도 초과 시 (burst 상황)
    await asyncio.sleep(1)
    ...
except ccxt.NetworkError:
    # 네트워크 오류 — tenacity로 재시도
    ...
```

---

## 3. Upbit (업비트) — CCXT 기반

**공식 문서:** https://docs.upbit.com  
**CCXT 문서:** https://docs.ccxt.com/#/exchanges/upbit  
**업비트 CCXT 가이드:** https://global-docs.upbit.com/docs/ccxt-library-integration-guide  
**구현 방식:** `ccxt.async_support.upbit` — REST + WebSocket 모두 CCXT 사용

### 3.1 어댑터 구현

```python
# bot_engine/exchange_adapters/upbit.py
import ccxt.async_support as ccxt
from .base import CcxtExchangeAdapter

class UpbitAdapter(CcxtExchangeAdapter):
    """Upbit 거래소 어댑터 — CCXT 기반."""

    def _build_exchange(self, config: dict) -> ccxt.upbit:
        return ccxt.upbit({
            **config,
            "options": {
                "defaultType": "spot",
            },
        })
```

### 3.2 심볼 형식

| 내부 표준 (CCXT) | 업비트 원본 형식 | 비고 |
|----------------|---------------|------|
| `BTC/KRW` | `KRW-BTC` | CCXT가 자동 변환 |
| `ETH/KRW` | `KRW-ETH` | CCXT가 자동 변환 |
| `BTC/USDT` | `USDT-BTC` | 글로벌 마켓 |

> 코드에서는 항상 CCXT 표준 형식(`BTC/KRW`)을 사용하세요. CCXT가 업비트 API 전송 시 `KRW-BTC`로 자동 변환합니다.

### 3.3 주요 CCXT 메서드 매핑

| 기능 | CCXT 메서드 | 내부 래퍼 |
|------|------------|---------|
| 잔고 조회 | `fetch_balance()` | `get_balance()` |
| 현재가 | `fetch_ticker(symbol)` | `get_ticker()` |
| 호가 | `fetch_order_book(symbol, limit)` | `get_orderbook()` |
| 지정가 주문 | `create_order(symbol, 'limit', side, amount, price)` | `place_order()` |
| 시장가 매수 | `create_order(symbol, 'market', 'buy', None, cost)` | `place_order()` |
| 시장가 매도 | `create_order(symbol, 'market', 'sell', amount)` | `place_order()` |
| 주문 취소 | `cancel_order(id, symbol)` | `cancel_order()` |
| 주문 조회 | `fetch_order(id, symbol)` | `get_order()` |
| 실시간 가격 | `watch_ticker(symbol)` | `price_stream()` |
| 주문 체결 이벤트 | `watch_orders()` | `order_update_stream()` |

> ⚠️ **업비트 시장가 매수 주의:** 업비트 시장가 매수는 수량(qty)이 아닌 금액(KRW)을 기준으로 합니다. CCXT `create_order`에서 `amount` 대신 `cost` 파라미터를 사용하거나 `params={"cost": krw_amount}`로 전달합니다.

### 3.4 Rate Limit

CCXT `enableRateLimit: True` 설정으로 자동 처리됩니다.

| 유형 | 한도 | CCXT 처리 |
|------|------|-----------|
| 주문 관련 (인증) | 10 req/sec, 200 req/min | 자동 대기 |
| 조회 (인증) | 30 req/sec, 900 req/min | 자동 대기 |
| Public | 10 req/sec | 자동 대기 |

### 3.5 예외 처리

업비트는 Binance와 동일한 CCXT 예외 계층을 사용합니다. 섹션 2.6 참고.

```python
# 업비트 특이사항: 시장가 매수 금액 기준
try:
    order = await adapter._exchange.create_order(
        symbol="BTC/KRW",
        type="market",
        side="buy",
        amount=None,
        price=None,
        params={"cost": 10000},  # 10,000 KRW 어치 매수
    )
except ccxt.InvalidOrder as e:
    # 최소 주문금액(5,000 KRW) 미만 등
    ...
```

---

## 4. 한국투자증권 KIS

**공식 문서:** https://apiportal.koreainvestment.com  
**Base URL (Real):** `https://openapi.koreainvestment.com:9443`  
**Base URL (Mock):** `https://openapivts.koreainvestment.com:29443`

### 4.1 인증

| 항목 | 내용 |
|------|------|
| 방식 | OAuth 2.0 (App Key + App Secret → Access Token 발급) |
| 토큰 유효기간 | 24시간 |
| 갱신 방법 | 만료 전 재발급 (자동 갱신 로직 구현 필요) |

```python
# 토큰 발급
POST /oauth2/tokenP
{
  "grant_type": "client_credentials",
  "appkey": "{app_key}",
  "appsecret": "{app_secret}"
}

# 응답
{
  "access_token": "Bearer {token}",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

**요청 헤더 공통 구조:**

```
authorization: Bearer {access_token}
appkey: {app_key}
appsecret: {app_secret}
tr_id: {거래ID}                # 요청별 거래 구분 코드
custtype: P                    # P: 개인
```

### 4.2 주요 REST API 엔드포인트

| 기능 | Method | Endpoint | tr_id |
|------|--------|----------|-------|
| 주식 현재가 | GET | `/uapi/domestic-stock/v1/quotations/inquire-price` | `FHKST01010100` |
| 계좌 잔고 | GET | `/uapi/domestic-stock/v1/trading/inquire-balance` | `TTTC8434R` (Real) / `VTTC8434R` (Mock) |
| 주식 주문 | POST | `/uapi/domestic-stock/v1/trading/order-cash` | `TTTC0802U` 매수 / `TTTC0801U` 매도 |
| 주문 취소 | POST | `/uapi/domestic-stock/v1/trading/order-rvsecncl` | `TTTC0803U` |
| 주문 조회 | GET | `/uapi/domestic-stock/v1/trading/inquire-psbl-order` | `TTTC8908R` |
| 당일 체결 내역 | GET | `/uapi/domestic-stock/v1/trading/inquire-daily-ccld` | `TTTC8001R` |

**주식 주문 파라미터:**

```json
{
  "CANO": "계좌번호 앞 8자리",
  "ACNT_PRDT_CD": "01",
  "PDNO": "005930",
  "ORD_DVSN": "00",        // 00: 지정가, 01: 시장가
  "ORD_QTY": "10",
  "ORD_UNPR": "70000"      // 지정가 (시장가는 "0")
}
```

### 4.3 WebSocket (실시간 시세)

KIS는 WebSocket을 통해 실시간 체결가, 호가 수신을 지원합니다.

**접속 키 발급:**

```python
POST /oauth2/Approval
{
  "grant_type": "client_credentials",
  "appkey": "{app_key}",
  "secretkey": "{app_secret}"
}
# → approval_key 발급 (WebSocket 인증용)
```

**WebSocket URL:** `ws://ops.koreainvestment.com:21000`

```json
// 구독 메시지 (주식 체결가)
{
  "header": {
    "approval_key": "{approval_key}",
    "custtype": "P",
    "tr_type": "1",
    "content-type": "utf-8"
  },
  "body": {
    "input": {
      "tr_id": "H0STCNT0",   // 주식 체결 통보
      "tr_key": "005930"      // 종목코드
    }
  }
}
```

### 4.4 Rate Limit

| 유형 | 한도 |
|------|------|
| 초당 요청 | 20 req/sec |
| WebSocket 구독 | 최대 40개 종목 동시 구독 |

---

## 5. 키움증권 REST API

**공식 포털:** https://openapi.kiwoom.com  
**Base URL (Real):** `https://openapi.kiwoom.com` (포털 로그인 후 정확한 도메인 확인 필요)  
**Base URL (Mock):** 포털 내 모의투자 서버 별도 제공

### 5.1 인증

| 항목 | 내용 |
|------|------|
| 방식 | App Key + Secret Key → Access Token 발급 |
| IP 화이트리스트 | 포털에서 허용 IP 사전 등록 필수 (미등록 IP 호출 차단) |
| 토큰 유효기간 | 포털 문서 기준 확인 필요 (KIS와 유사하게 24시간 추정) |

```python
# 토큰 발급
POST /oauth2/token
{
  "grant_type": "client_credentials",
  "appkey": "{app_key}",
  "secretkey": "{secret_key}"
}
```

**공통 헤더:**

```
authorization: Bearer {access_token}
appkey: {app_key}
appsecret: {secret_key}
tr_id: {거래ID}
```

### 5.2 주요 REST API 엔드포인트

키움 REST API는 KIS와 유사한 구조를 가집니다. 포털 내 API 가이드 기준으로 아래 기능을 활용합니다.

| 기능 | 설명 |
|------|------|
| 현재가 조회 | 국내 주식 실시간 현재가 |
| 계좌 잔고 | 계좌 평가 잔고 및 보유 종목 조회 |
| 주식 주문 | 매수/매도 주문 발행 (지정가, 시장가) |
| 주문 취소/정정 | 미체결 주문 취소 및 가격 정정 |
| 체결 내역 | 당일 체결 내역 조회 |
| 조건 검색 | 영웅문4 조건검색 결과 조회 (키움 REST API 특화 기능) |

> ⚠️ **개발 전 반드시 확인:** 키움 REST API는 2025년 출시된 신규 서비스로, 포털(https://openapi.kiwoom.com)의 최신 API 가이드와 공지사항을 반드시 확인하고 구현해야 합니다. 엔드포인트 및 파라미터가 변경될 수 있습니다.

### 5.3 WebSocket (실시간 시세)

포털 내 API 가이드의 WebSocket 연동 방법을 기준으로 구현합니다. KIS와 유사하게 접속키 발급 후 연결하는 방식으로 예상됩니다.

### 5.4 Rate Limit

포털 공지사항에서 최신 Rate Limit 정책 확인 필요.

---

## 6. 거래소 공통 데이터 정규화

거래소마다 응답 형식이 다르지만, **Binance·Upbit은 CCXT가 통합 형식으로 자동 정규화**합니다.
KIS·키움은 직접 파싱이 필요합니다.

### 6.1 Symbol 형식

| 거래소 | 코드 내부 표준 (CCXT 형식) | 거래소 원본 | CCXT 자동 변환 |
|--------|--------------------------|------------|-------------|
| Binance | `BTC/USDT` | `BTCUSDT` | ✅ 자동 |
| Upbit | `BTC/KRW` | `KRW-BTC` | ✅ 자동 |
| KIS | `005930` (종목코드) | `005930` | 해당 없음 |
| Kiwoom | `005930` (종목코드) | `005930` | 해당 없음 |

> Binance·Upbit은 CCXT를 통해 `BTC/USDT`, `BTC/KRW` 형식으로 통일합니다. 직접 `BTCUSDT`이나 `KRW-BTC` 형식을 코드에 사용하지 마세요. DB 저장 시에도 CCXT 표준 형식을 기준으로 합니다.

### 6.2 주문 상태 정규화

CCXT는 Binance·Upbit 주문 상태를 이미 통합 형식으로 반환합니다.

| 공통 상태 (CCXT) | Binance 원본 | Upbit 원본 | KIS | Kiwoom |
|-----------------|-------------|-----------|-----|--------|
| `open` | `NEW` | `wait` | 접수 | 접수 |
| `partially_filled` | `PARTIALLY_FILLED` | `watch` | 부분체결 | 부분체결 |
| `closed` | `FILLED` | `done` | 체결 | 체결 |
| `canceled` | `CANCELED` | `cancel` | 취소 | 취소 |

> CCXT `fetch_order()` / `watch_orders()` 응답의 `status` 필드는 이미 위 통합 값으로 반환됩니다.
> KIS·키움은 직접 파싱 후 위 공통 값으로 변환합니다.

### 6.3 거래소별 잔고 정규화

Binance·Upbit은 `CcxtExchangeAdapter.get_balance()` 공통 구현으로 자동 처리됩니다. (섹션 1.1-A 참고)

KIS 잔고 직접 파싱 예시:

```python
# KIS 응답 → BalanceItem 변환
def parse_kis_balance(raw: dict) -> list[BalanceItem]:
    items = []
    for holding in raw.get("output1", []):
        items.append(BalanceItem(
            asset=holding["pdno"],             # 종목코드
            free=Decimal(holding["hldg_qty"]), # 보유수량
            locked=Decimal(holding["ord_psbl_qty"]),  # 주문가능수량
        ))
    # KRW 잔고
    output2 = raw.get("output2", [{}])[0]
    items.append(BalanceItem(
        asset="KRW",
        free=Decimal(output2.get("prvs_rcdv_amt", "0")),
        locked=Decimal("0"),
    ))
    return items
```

---

## 7. Rate Limit 관리 전략

### 7.1 Binance·Upbit — CCXT 자동 처리

CCXT `enableRateLimit: True` 설정 시 라이브러리가 Rate Limit을 자동으로 준수합니다.
별도 애플리케이션 레벨 Rate Limiter 구현이 불필요합니다.

```python
# ✅ CCXT 생성 시 enableRateLimit 반드시 활성화
exchange = ccxt.binance({
    "apiKey": api_key,
    "secret": secret,
    "enableRateLimit": True,   # Rate Limit 자동 처리 활성화
})
```

### 7.2 KIS·키움 — Redis 슬라이딩 윈도우 직접 구현

CCXT 미사용 거래소는 직접 Rate Limit을 관리합니다.

```python
import redis.asyncio as aioredis

class RateLimiter:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def check(self, key: str, limit: int, window_sec: int) -> bool:
        """True: 통과, False: 제한 초과"""
        pipe = self.redis.pipeline()
        now = time.time()
        window_start = now - window_sec

        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window_sec + 1)
        results = await pipe.execute()

        return results[2] <= limit

# 사용 예시 (KIS)
if not await limiter.check(f"kis:orders:{user_id}", limit=20, window_sec=1):
    raise RateLimitError("KIS 주문 Rate Limit 초과")
```

### 7.3 거래소별 Rate Limit 요약

| 거래소 | 주문 | 조회 | 초과 시 | 관리 방법 |
|--------|------|------|---------|---------|
| Binance | 10/sec, 100,000/24h | 1200 weight/min | HTTP 429 | CCXT 자동 |
| Upbit | 10/sec, 200/min | 30/sec | HTTP 429 | CCXT 자동 |
| KIS | 20/sec | 20/sec | HTTP 400 | Redis 직접 구현 |
| Kiwoom | 포털 확인 필요 | 포털 확인 필요 | — | Redis 직접 구현 |

### 7.4 CCXT 예외 → 공통 예외 변환

```python
import ccxt
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def call_with_retry(coro):
    """CCXT 네트워크 오류 시 지수 백오프 재시도."""
    try:
        return await coro
    except ccxt.RateLimitExceeded:
        await asyncio.sleep(1)
        raise
    except ccxt.AuthenticationError:
        raise  # 인증 오류는 재시도 없이 즉시 실패
    except ccxt.NetworkError:
        raise  # tenacity가 재시도
```

---

## 8. 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| v1.0 | 2025년 | 최초 작성 | PM |
| v1.1 | 2025년 | 키움증권 연동 구조 변경 — Windows Bridge Server 제거, 키움 REST API 직접 연동으로 전면 수정 | PM |
| v1.2 | 2025년 | Binance·Upbit 연동 방식 변경 — 직접 REST/WebSocket 구현 → CCXT(`ccxt.async_support`) 사용. 섹션 2·3 전면 재작성. 공통 베이스 클래스 `CcxtExchangeAdapter` 추가. 데이터 정규화 섹션 CCXT 기준으로 재작성 | PM |
| v1.3 | 2025년 | ccxt 라이브러리 설명 보강 — 섹션 1.0에 CCXT 소개·설치 방법·임포트 패턴(v4 이후 async_support 통합) 추가. Binance 어댑터에 get_balance() 구현 및 price_stream/order_update_stream 패턴 명시. 테스트넷 set_sandbox_mode() 방식 문서화. orjson·coincurve 성능 최적화 옵션 추가 | PM |

---

*각 거래소 API는 변경될 수 있으므로, 구현 전 공식 문서 최신 버전을 반드시 확인합니다.*  
*특히 키움 REST API는 신규 서비스이므로 포털 공지사항을 주기적으로 확인합니다.*
