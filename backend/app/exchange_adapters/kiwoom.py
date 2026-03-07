"""키움증권 REST API 어댑터 — httpx 직접 구현.

인증: App Key + Secret Key → Access Token 발급
IP 화이트리스트: 포털(https://openapi.kiwoom.com)에서 사전 등록 필수.

참고: 키움 REST API는 2025년 출시된 신규 서비스입니다.
엔드포인트/파라미터는 포털의 최신 API 가이드를 반드시 확인하고 구현합니다.

extra_params (ExchangeAccount.extra_params_enc 복호화 후):
  {
    "account_no": "계좌번호",
    "is_mock": false
  }
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncGenerator

import httpx

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

_BASE_URL = "https://openapi.kiwoom.com"


class KiwoomAdapter(AbstractExchangeAdapter):
    """키움증권 REST API 어댑터."""

    def __init__(
        self,
        app_key: str,
        secret_key: str,
        account_no: str,
        is_mock: bool = False,
    ) -> None:
        self._app_key = app_key
        self._secret_key = secret_key
        self._account_no = account_no
        self._is_mock = is_mock
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def _ensure_token(self) -> str:
        now = datetime.now(UTC)
        if (
            self._access_token is None
            or self._token_expires_at is None
            or now >= self._token_expires_at - timedelta(minutes=5)
        ):
            await self._refresh_token()
        assert self._access_token is not None
        return self._access_token

    async def _refresh_token(self) -> None:
        resp = await self._client.post(
            f"{_BASE_URL}/oauth2/token",
            json={
                "grant_type": "client_credentials",
                "appkey": self._app_key,
                "secretkey": self._secret_key,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        expires_in = int(data.get("expires_in", 86400))
        self._token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

    def _headers(self, tr_id: str, token: str) -> dict[str, str]:
        return {
            "authorization": f"Bearer {token}",
            "appkey": self._app_key,
            "appsecret": self._secret_key,
            "tr_id": tr_id,
            "Content-Type": "application/json; charset=utf-8",
        }

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
        resp = await self._client.get(
            f"{_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance",
            headers=self._headers("TTTC8434R", token),
            params={"CANO": self._account_no},
        )
        resp.raise_for_status()
        raw = resp.json()
        items: list[BalanceItem] = []
        for holding in raw.get("output1", []):
            qty = Decimal(holding.get("hldg_qty", "0"))
            if qty > Decimal("0"):
                items.append(
                    BalanceItem(
                        asset=holding.get("pdno", ""),
                        free=Decimal(holding.get("ord_psbl_qty", "0")),
                        locked=qty - Decimal(holding.get("ord_psbl_qty", "0")),
                    )
                )
        return items

    async def get_ticker(self, symbol: str) -> TickerData:
        token = await self._ensure_token()
        resp = await self._client.get(
            f"{_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
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
        tr_id = "TTTC0802U" if is_buy else "TTTC0801U"
        ord_dvsn = "01" if order.order_type == "market" else "00"
        resp = await self._client.post(
            f"{_BASE_URL}/uapi/domestic-stock/v1/trading/order-cash",
            headers=self._headers(tr_id, token),
            json={
                "CANO": self._account_no,
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
        resp = await self._client.post(
            f"{_BASE_URL}/uapi/domestic-stock/v1/trading/order-cancel",
            headers=self._headers("TTTC0803U", token),
            json={
                "CANO": self._account_no,
                "ORGN_ODNO": exchange_order_id,
                "PDNO": symbol,
                "RVSE_CNCL_DVSN_CD": "02",
                "ORD_QTY": "0",
                "QTY_ALL_ORD_YN": "Y",
            },
        )
        resp.raise_for_status()
        return True

    async def get_order(self, exchange_order_id: str, symbol: str) -> OrderResponse:
        token = await self._ensure_token()
        resp = await self._client.get(
            f"{_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
            headers=self._headers("TTTC8001R", token),
            params={
                "CANO": self._account_no,
                "ODNO": exchange_order_id,
                "INQR_STRT_DT": datetime.now(UTC).strftime("%Y%m%d"),
                "INQR_END_DT": datetime.now(UTC).strftime("%Y%m%d"),
            },
        )
        resp.raise_for_status()
        raw = resp.json()
        items = raw.get("output1", [])
        item = items[0] if items else {}
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
        token = await self._ensure_token()
        resp = await self._client.get(
            f"{_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-asking-price",
            headers=self._headers("FHKST01010200", token),
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        )
        resp.raise_for_status()
        raw = resp.json().get("output1", {})
        n = min(depth, 10)
        bids = [
            [Decimal(raw.get(f"bidp{i}", "0")), Decimal(raw.get(f"bidp_rsqn{i}", "0"))]
            for i in range(1, n + 1)
        ]
        asks = [
            [Decimal(raw.get(f"askp{i}", "0")), Decimal(raw.get(f"askp_rsqn{i}", "0"))]
            for i in range(1, n + 1)
        ]
        return OrderBook(bids=bids, asks=asks)

    async def _get_ws_approval_key(self) -> str:
        """WebSocket 접속키 발급."""
        resp = await self._client.post(
            f"{_BASE_URL}/oauth2/approval",
            json={
                "grant_type": "client_credentials",
                "appkey": self._app_key,
                "secretkey": self._secret_key,
            },
        )
        resp.raise_for_status()
        return resp.json()["approval_key"]

    async def price_stream(self, symbol: str) -> AsyncGenerator[PriceTick, None]:
        """키움 WebSocket 실시간 체결가 스트림.

        키움 REST API WebSocket은 KIS와 유사한 구조를 사용합니다.
        - 접속키 발급: POST /oauth2/approval
        - WebSocket URL: wss://openapi.kiwoom.com:9443/ws
        - 구독 TR: H0STCNT0 (주식체결)
        - 데이터: pipe(|) 구분 → 4번째 필드 caret(^) 구분
          [2]: 현재가(STCK_PRPR)

        ⚠️ 키움 REST API는 신규 서비스(2025년)이므로 포털
           (https://openapi.kiwoom.com) 최신 API 가이드를 반드시 확인하세요.
        """
        import json
        import websockets  # type: ignore[import-untyped]

        approval_key = await self._get_ws_approval_key()
        ws_url = "wss://openapi.kiwoom.com:9443/ws"
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
                if not isinstance(message, str):
                    continue
                parts = message.split("|")
                if len(parts) < 4 or parts[1] != "H0STCNT0":
                    continue
                fields = parts[3].split("^")
                price = Decimal(fields[2]) if len(fields) > 2 and fields[2] else Decimal("0")
                yield PriceTick(
                    symbol=symbol,
                    price=price,
                    timestamp=datetime.now(UTC),
                )

    async def order_update_stream(self) -> AsyncGenerator[OrderResponse, None]:
        """키움 WebSocket 실시간 체결통보 스트림.

        - 구독 TR: H0STCNI0 (체결통보) — KIS와 동일한 TR ID 사용
        - 구독 키: 계좌번호
        - 데이터 필드(^ 구분, KIS H0STCNI0와 동일 구조):
          [2]  ODNO (주문번호)
          [5]  PDNO (종목코드)
          [6]  ORD_DVSN_CD (01=매도, 02=매수)
          [7]  CNTG_QTY (체결수량)
          [8]  CNTG_UNPR (체결단가)
          [11] CNTG_YN (체결여부 Y/N)
          [14] ORD_QTY (주문수량)

        ⚠️ 실제 TR ID 및 필드 구조는 포털 최신 API 가이드에서 확인하세요.
        """
        import json
        import websockets  # type: ignore[import-untyped]

        approval_key = await self._get_ws_approval_key()
        ws_url = "wss://openapi.kiwoom.com:9443/ws"
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
                    "tr_key": self._account_no,
                }
            },
        }
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps(subscribe_msg))
            async for message in ws:
                if not isinstance(message, str):
                    continue
                parts = message.split("|")
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
