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
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncGenerator, Any

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

_REAL_BASE = "https://openapi.koreainvestment.com:9443"
_MOCK_BASE = "https://openapivts.koreainvestment.com:29443"


class KisAdapter(AbstractExchangeAdapter):
    """한국투자증권 REST API 어댑터."""

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
            self._access_token is None
            or self._token_expires_at is None
            or now >= self._token_expires_at - timedelta(minutes=5)
        ):
            await self._refresh_token()
        assert self._access_token is not None
        return self._access_token

    async def _refresh_token(self) -> None:
        resp = await self._client.post(
            f"{self._base_url}/oauth2/tokenP",
            json={
                "grant_type": "client_credentials",
                "appkey": self._app_key,
                "appsecret": self._app_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expires_at = datetime.now(UTC) + timedelta(
            seconds=int(data.get("expires_in", 86400))
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
        resp.raise_for_status()
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
        # KIS 실시간 체결통보는 WebSocket H0STCNI0 사용 (구현 예정)
        raise NotImplementedError("KIS order_update_stream is not yet implemented")
        yield  # make it a generator


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
