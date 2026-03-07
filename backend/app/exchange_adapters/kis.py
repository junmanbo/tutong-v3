"""한국투자증권(KIS) 거래소 어댑터 — httpx 직접 구현.

인증: OAuth 2.0 (App Key + App Secret → Access Token, 24시간 유효)
Base URL (Real):  https://openapi.koreainvestment.com:9443
Base URL (Mock):  https://openapivts.koreainvestment.com:29443

extra_params (ExchangeAccount.extra_params_enc 복호화 후):
  {
    "CANO": "계좌번호 앞 8자리",
    "ACNT_PRDT_CD": "01",
    "is_mock": false
  }
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncGenerator, Any

import httpx
import redis as redis_lib

from app.exchange_adapters.base import (
    AbstractExchangeAdapter,
    BalanceItem,
    OrderBook,
    OrderRequest,
    OrderResponse,
    PriceTick,
    TickerData,
)

UTC = timezone.utc
logger = logging.getLogger(__name__)

_REAL_BASE = "https://openapi.koreainvestment.com:9443"
_MOCK_BASE = "https://openapivts.koreainvestment.com:29443"

_TOKEN_RETRY_ERROR_CODE = "EGW00133"
_TOKEN_RETRY_DELAY_SECONDS = 1.2
_TOKEN_REUSE_MARGIN_SECONDS = 300
_REDIS_KEY_PREFIX = "kis:token"


class KisApiError(Exception):
    def __init__(
        self,
        *,
        endpoint: str,
        status_code: int,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.status_code = status_code
        self.error_code = error_code
        self.error_message = error_message
        detail = f"KIS API error {status_code} at {endpoint}"
        if error_code:
            detail += f" [{error_code}]"
        if error_message:
            detail += f": {error_message}"
        super().__init__(detail)


class KisAdapter(AbstractExchangeAdapter):
    """한국투자증권 REST API 어댑터."""
    _process_token_cache: dict[str, tuple[str, datetime]] = {}
    _token_locks: dict[str, asyncio.Lock] = {}
    _redis_client: redis_lib.Redis | None = None

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        cano: str,
        acnt_prdt_cd: str = "01",
        is_mock: bool = False,
    ) -> None:
        self._app_key = app_key
        self._app_secret = app_secret
        self._cano = cano
        self._acnt_prdt_cd = acnt_prdt_cd
        self._base_url = _MOCK_BASE if is_mock else _REAL_BASE
        self._is_mock = is_mock
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        await self._client.aclose()

    # ── 토큰 관리 ─────────────────────────────────────────────────────────────

    async def _ensure_token(self) -> str:
        """Access Token 유효성 확인 후 필요 시 재발급."""
        now = datetime.now(UTC)
        if (
            self._access_token is not None
            and self._token_expires_at is not None
            and now < self._token_expires_at - timedelta(seconds=_TOKEN_REUSE_MARGIN_SECONDS)
        ):
            return self._access_token

        cache_key = self._token_cache_key()
        cached = self._read_token_from_process_cache(cache_key)
        if cached:
            self._access_token, self._token_expires_at = cached
            return self._access_token

        cached = self._read_token_from_redis_cache(cache_key)
        if cached:
            self._access_token, self._token_expires_at = cached
            self._write_token_to_process_cache(
                cache_key=cache_key,
                token=self._access_token,
                expires_at=self._token_expires_at,
            )
            return self._access_token

        lock = self._token_locks.setdefault(cache_key, asyncio.Lock())
        async with lock:
            cached = self._read_token_from_process_cache(cache_key)
            if cached:
                self._access_token, self._token_expires_at = cached
                return self._access_token

            cached = self._read_token_from_redis_cache(cache_key)
            if cached:
                self._access_token, self._token_expires_at = cached
                self._write_token_to_process_cache(
                    cache_key=cache_key,
                    token=self._access_token,
                    expires_at=self._token_expires_at,
                )
                return self._access_token

            await self._refresh_token()
            assert self._access_token is not None
            assert self._token_expires_at is not None
            self._write_token_to_process_cache(
                cache_key=cache_key,
                token=self._access_token,
                expires_at=self._token_expires_at,
            )
            self._write_token_to_redis_cache(
                cache_key=cache_key,
                token=self._access_token,
                expires_at=self._token_expires_at,
            )
        assert self._access_token is not None
        return self._access_token

    async def _refresh_token(self) -> None:
        endpoint = f"{self._base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
        }
        resp = await self._client.post(endpoint, json=payload)
        if resp.status_code >= 400:
            error = self._parse_error_response(endpoint=endpoint, response=resp)
            if (
                error.status_code == 403
                and error.error_code == _TOKEN_RETRY_ERROR_CODE
            ):
                await asyncio.sleep(_TOKEN_RETRY_DELAY_SECONDS)
                resp = await self._client.post(endpoint, json=payload)
                if resp.status_code >= 400:
                    raise self._parse_error_response(endpoint=endpoint, response=resp)
            else:
                raise error
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expires_at = datetime.now(UTC) + timedelta(
            seconds=int(data.get("expires_in", 86400))
        )

    def _token_cache_key(self) -> str:
        app_hash = hashlib.sha256(self._app_key.encode()).hexdigest()[:16]
        mode = "mock" if self._is_mock else "real"
        return f"{_REDIS_KEY_PREFIX}:{mode}:{app_hash}"

    @classmethod
    def _redis(cls) -> redis_lib.Redis | None:
        if cls._redis_client is not None:
            return cls._redis_client
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            return None
        try:
            cls._redis_client = redis_lib.from_url(redis_url, decode_responses=True)
        except Exception as exc:
            logger.warning("KIS token redis init failed: %s", exc)
            cls._redis_client = None
        return cls._redis_client

    @classmethod
    def _write_token_to_process_cache(
        cls, *, cache_key: str, token: str, expires_at: datetime
    ) -> None:
        cls._process_token_cache[cache_key] = (token, expires_at)

    @classmethod
    def _read_token_from_process_cache(
        cls, cache_key: str
    ) -> tuple[str, datetime] | None:
        cached = cls._process_token_cache.get(cache_key)
        if not cached:
            return None
        token, expires_at = cached
        if datetime.now(UTC) >= expires_at - timedelta(seconds=_TOKEN_REUSE_MARGIN_SECONDS):
            cls._process_token_cache.pop(cache_key, None)
            return None
        return token, expires_at

    @classmethod
    def _write_token_to_redis_cache(
        cls, *, cache_key: str, token: str, expires_at: datetime
    ) -> None:
        redis_client = cls._redis()
        if redis_client is None:
            return
        ttl = int((expires_at - datetime.now(UTC)).total_seconds()) - _TOKEN_REUSE_MARGIN_SECONDS
        if ttl <= 0:
            return
        try:
            redis_client.setex(
                cache_key,
                ttl,
                json.dumps(
                    {"access_token": token, "expires_at": expires_at.isoformat()}
                ),
            )
        except Exception as exc:
            logger.warning("KIS token redis write failed: %s", exc)

    @classmethod
    def _read_token_from_redis_cache(
        cls, cache_key: str
    ) -> tuple[str, datetime] | None:
        redis_client = cls._redis()
        if redis_client is None:
            return None
        try:
            raw = redis_client.get(cache_key)
            if not raw:
                return None
            data = json.loads(raw)
            token = data.get("access_token")
            expires_at_raw = data.get("expires_at")
            if not token or not expires_at_raw:
                return None
            expires_at = datetime.fromisoformat(expires_at_raw)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if datetime.now(UTC) >= expires_at - timedelta(seconds=_TOKEN_REUSE_MARGIN_SECONDS):
                return None
            return token, expires_at
        except Exception as exc:
            logger.warning("KIS token redis read failed: %s", exc)
            return None

    @staticmethod
    def _parse_error_response(*, endpoint: str, response: httpx.Response) -> KisApiError:
        error_code: str | None = None
        error_message: str | None = None
        try:
            data = response.json()
            if isinstance(data, dict):
                error_code = (
                    data.get("error_code")
                    or data.get("msg_cd")
                    or data.get("rt_cd")
                )
                error_message = (
                    data.get("error_description")
                    or data.get("msg1")
                )
        except Exception:
            error_message = response.text[:300]

        return KisApiError(
            endpoint=endpoint,
            status_code=response.status_code,
            error_code=error_code,
            error_message=error_message,
        )

    def _headers(self, tr_id: str, token: str) -> dict[str, str]:
        return {
            "authorization": f"Bearer {token}",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
            "tr_id": tr_id,
            "custtype": "P",
            "Content-Type": "application/json; charset=utf-8",
        }

    # ── 인터페이스 구현 ───────────────────────────────────────────────────────

    async def validate_credentials(self) -> bool:
        try:
            await self._ensure_token()
            return True
        except Exception:
            return False
        finally:
            await self.close()

    async def get_balance(self) -> list[BalanceItem]:
        token = await self._ensure_token()
        tr_id = "VTTC8434R" if self._is_mock else "TTTC8434R"
        resp = await self._client.get(
            f"{self._base_url}/uapi/domestic-stock/v1/trading/inquire-balance",
            headers=self._headers(tr_id, token),
            params={
                "CANO": self._cano,
                "ACNT_PRDT_CD": self._acnt_prdt_cd,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )
        if resp.status_code >= 400:
            raise self._parse_error_response(
                endpoint=f"{self._base_url}/uapi/domestic-stock/v1/trading/inquire-balance",
                response=resp,
            )
        return _parse_kis_balance(resp.json())

    async def get_ticker(self, symbol: str) -> TickerData:
        """symbol: 종목코드 (예: '005930')"""
        token = await self._ensure_token()
        resp = await self._client.get(
            f"{self._base_url}/uapi/domestic-stock/v1/quotations/inquire-price",
            headers=self._headers("FHKST01010100", token),
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        )
        resp.raise_for_status()
        data = resp.json().get("output", {})
        price = Decimal(data.get("stck_prpr", "0"))
        return TickerData(
            symbol=symbol,
            price=price,
            bid=Decimal(data.get("bidp", "0")),
            ask=Decimal(data.get("askp", "0")),
            timestamp=datetime.now(UTC),
        )

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        token = await self._ensure_token()
        is_buy = order.side == "buy"
        if self._is_mock:
            tr_id = "VTTC0802U" if is_buy else "VTTC0801U"
        else:
            tr_id = "TTTC0802U" if is_buy else "TTTC0801U"

        ord_dvsn = "01" if order.order_type == "market" else "00"
        resp = await self._client.post(
            f"{self._base_url}/uapi/domestic-stock/v1/trading/order-cash",
            headers=self._headers(tr_id, token),
            json={
                "CANO": self._cano,
                "ACNT_PRDT_CD": self._acnt_prdt_cd,
                "PDNO": order.symbol,
                "ORD_DVSN": ord_dvsn,
                "ORD_QTY": str(int(order.qty or 0)),
                "ORD_UNPR": str(int(order.price or 0)),
            },
        )
        resp.raise_for_status()
        raw = resp.json()
        output = raw.get("output", {})
        return OrderResponse(
            exchange_order_id=output.get("ODNO", ""),
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            status="open",
            requested_qty=order.qty,
            filled_qty=Decimal("0"),
            avg_fill_price=None,
            fee=Decimal("0"),
            fee_currency="KRW",
            raw=raw,
        )

    async def cancel_order(self, exchange_order_id: str, symbol: str) -> bool:
        token = await self._ensure_token()
        tr_id = "VTTC0803U" if self._is_mock else "TTTC0803U"
        resp = await self._client.post(
            f"{self._base_url}/uapi/domestic-stock/v1/trading/order-rvsecncl",
            headers=self._headers(tr_id, token),
            json={
                "CANO": self._cano,
                "ACNT_PRDT_CD": self._acnt_prdt_cd,
                "KRX_FWDG_ORD_ORGNO": "",
                "ORGN_ODNO": exchange_order_id,
                "ORD_DVSN": "02",
                "RVSE_CNCL_DVSN_CD": "02",
                "ORD_QTY": "0",
                "ORD_UNPR": "0",
                "PDNO": symbol,
                "QTY_ALL_ORD_YN": "Y",
            },
        )
        resp.raise_for_status()
        return True

    async def get_order(self, exchange_order_id: str, symbol: str) -> OrderResponse:
        # KIS는 주문번호로 단건 조회하는 별도 API가 없어 당일 체결 내역에서 조회
        token = await self._ensure_token()
        tr_id = "VTTC8001R" if self._is_mock else "TTTC8001R"
        resp = await self._client.get(
            f"{self._base_url}/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
            headers=self._headers(tr_id, token),
            params={
                "CANO": self._cano,
                "ACNT_PRDT_CD": self._acnt_prdt_cd,
                "INQR_STRT_DT": datetime.now(UTC).strftime("%Y%m%d"),
                "INQR_END_DT": datetime.now(UTC).strftime("%Y%m%d"),
                "SLL_BUY_DVSN_CD": "00",
                "INQR_DVSN": "00",
                "PDNO": symbol,
                "CCLD_DVSN": "00",
                "ORD_GNO_BRNO": "",
                "ODNO": exchange_order_id,
                "INQR_DVSN_3": "00",
                "INQR_DVSN_1": "",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )
        resp.raise_for_status()
        raw = resp.json()
        items = raw.get("output1", [])
        item: dict[str, Any] = items[0] if items else {}
        return OrderResponse(
            exchange_order_id=exchange_order_id,
            symbol=symbol,
            side="buy" if item.get("sll_buy_dvsn_cd") == "02" else "sell",
            order_type="limit",
            status="closed" if item else "open",
            requested_qty=Decimal(item.get("ord_qty", "0")),
            filled_qty=Decimal(item.get("tot_ccld_qty", "0")),
            avg_fill_price=Decimal(item.get("avg_prvs", "0")) if item else None,
            fee=Decimal("0"),
            fee_currency="KRW",
            raw=raw,
        )

    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        # KIS 호가는 별도 endpoint 사용 (FHKST01010200)
        token = await self._ensure_token()
        resp = await self._client.get(
            f"{self._base_url}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
            headers=self._headers("FHKST01010200", token),
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        )
        resp.raise_for_status()
        raw = resp.json().get("output1", {})
        bids = [
            [Decimal(raw.get(f"bidp{i}", "0")), Decimal(raw.get(f"bidp_rsqn{i}", "0"))]
            for i in range(1, min(depth + 1, 11))
        ]
        asks = [
            [Decimal(raw.get(f"askp{i}", "0")), Decimal(raw.get(f"askp_rsqn{i}", "0"))]
            for i in range(1, min(depth + 1, 11))
        ]
        return OrderBook(bids=bids, asks=asks)

    async def price_stream(self, symbol: str) -> AsyncGenerator[PriceTick, None]:
        """KIS WebSocket 실시간 체결가 스트림 (H0STCNT0)."""
        import json
        import websockets  # type: ignore[import-untyped]

        token = await self._ensure_token()
        # WebSocket 접속키 발급
        resp = await self._client.post(
            f"{self._base_url}/oauth2/Approval",
            json={
                "grant_type": "client_credentials",
                "appkey": self._app_key,
                "secretkey": self._app_secret,
            },
        )
        resp.raise_for_status()
        approval_key = resp.json()["approval_key"]

        ws_url = "ws://ops.koreainvestment.com:21000"
        subscribe_msg = {
            "header": {
                "approval_key": approval_key,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8",
            },
            "body": {"input": {"tr_id": "H0STCNT0", "tr_key": symbol}},
        }
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps(subscribe_msg))
            async for message in ws:
                data = message.split("|")
                if len(data) >= 4 and data[1] == "H0STCNT0":
                    fields = data[3].split("^")
                    price = Decimal(fields[2]) if len(fields) > 2 else Decimal("0")
                    yield PriceTick(
                        symbol=symbol,
                        price=price,
                        timestamp=datetime.now(UTC),
                    )

    async def order_update_stream(self) -> AsyncGenerator[OrderResponse, None]:
        """KIS WebSocket 실시간 체결통보 스트림 (H0STCNI0).

        구독 키: 계좌번호(CANO)
        데이터 형식: pipe(|) 구분 → 4번째 필드를 caret(^) 구분으로 파싱
        필드 순서 (^ 구분):
          [0]  CANO (계좌번호)
          [1]  ACNT_PRDT_CD (계좌상품코드)
          [2]  ODNO (주문번호)
          [3]  ORGN_ODNO (원주문번호)
          [4]  ORD_DVSN_NAME (주문구분명)
          [5]  PDNO (종목코드)
          [6]  ORD_DVSN_CD (01=매도, 02=매수)
          [7]  CNTG_QTY (체결수량)
          [8]  CNTG_UNPR (체결단가)
          [9]  STCK_CNTG_HOUR (체결시각)
          [10] RFUS_YN (거부여부 Y/N)
          [11] CNTG_YN (체결여부 Y=체결, N=접수)
          [14] ORD_QTY (주문수량)
        """
        import json
        import websockets  # type: ignore[import-untyped]

        token = await self._ensure_token()
        # WebSocket 접속키 발급
        resp = await self._client.post(
            f"{self._base_url}/oauth2/Approval",
            json={
                "grant_type": "client_credentials",
                "appkey": self._app_key,
                "secretkey": self._app_secret,
            },
        )
        resp.raise_for_status()
        approval_key = resp.json()["approval_key"]

        ws_url = "ws://ops.koreainvestment.com:21000"
        subscribe_msg = {
            "header": {
                "approval_key": approval_key,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8",
            },
            "body": {
                "input": {
                    "tr_id": "H0STCNI0",
                    "tr_key": self._cano,  # 계좌번호로 체결통보 구독
                }
            },
        }
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps(subscribe_msg))
            async for message in ws:
                if not isinstance(message, str):
                    continue
                parts = message.split("|")
                # 데이터 메시지: |H0STCNI0|{userid}|{fields}
                if len(parts) < 4 or parts[1] != "H0STCNI0":
                    continue
                fields = parts[3].split("^")
                if len(fields) < 12:
                    continue
                exchange_order_id = fields[2]
                symbol = fields[5]
                side = "buy" if fields[6] == "02" else "sell"
                cntg_qty = Decimal(fields[7]) if fields[7] else Decimal("0")
                cntg_price = Decimal(fields[8]) if fields[8] else Decimal("0")
                is_filled = fields[11] == "Y"
                ord_qty = Decimal(fields[14]) if len(fields) > 14 and fields[14] else Decimal("0")
                yield OrderResponse(
                    exchange_order_id=exchange_order_id,
                    symbol=symbol,
                    side=side,
                    order_type="limit",
                    status="closed" if is_filled else "open",
                    requested_qty=ord_qty,
                    filled_qty=cntg_qty,
                    avg_fill_price=cntg_price if is_filled else None,
                    fee=Decimal("0"),
                    fee_currency="KRW",
                    raw={"fields": fields},
                )


# ── 파싱 헬퍼 ─────────────────────────────────────────────────────────────────


def _parse_kis_balance(raw: dict) -> list[BalanceItem]:
    items: list[BalanceItem] = []
    for holding in raw.get("output1", []):
        qty = Decimal(holding.get("hldg_qty", "0"))
        if qty > Decimal("0"):
            items.append(
                BalanceItem(
                    asset=holding["pdno"],
                    free=Decimal(holding.get("ord_psbl_qty", "0")),
                    locked=qty - Decimal(holding.get("ord_psbl_qty", "0")),
                )
            )
    output2 = raw.get("output2", [{}])
    if output2:
        krw = Decimal(output2[0].get("prvs_rcdv_amt", "0"))
        if krw > Decimal("0"):
            items.append(BalanceItem(asset="KRW", free=krw, locked=Decimal("0")))
    return items
