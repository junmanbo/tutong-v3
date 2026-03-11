from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.exchange_adapters.base import OrderRequest
from app.exchange_adapters.kiwoom import KiwoomAdapter

UTC = timezone.utc


def _mock_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def _make_adapter() -> KiwoomAdapter:
    return KiwoomAdapter(
        app_key="app-key",
        secret_key="secret-key",
        account_no="12345678",
        is_mock=True,
    )


class TestTokenFlow:
    def test_ensure_token_reuses_valid_token(self) -> None:
        adapter = _make_adapter()
        adapter._access_token = "cached-token"
        adapter._token_expires_at = datetime.now(UTC) + timedelta(hours=1)
        adapter._refresh_token = AsyncMock()

        token = asyncio.run(adapter._ensure_token())
        assert token == "cached-token"
        adapter._refresh_token.assert_not_called()
        asyncio.run(adapter.close())

    def test_ensure_token_refreshes_when_missing(self) -> None:
        adapter = _make_adapter()
        adapter._access_token = None
        adapter._token_expires_at = None

        async def _refresh() -> None:
            adapter._access_token = "new-token"
            adapter._token_expires_at = datetime.now(UTC) + timedelta(hours=1)

        adapter._refresh_token = AsyncMock(side_effect=_refresh)

        token = asyncio.run(adapter._ensure_token())
        assert token == "new-token"
        adapter._refresh_token.assert_awaited_once()
        asyncio.run(adapter.close())


class TestAdapterMethods:
    def test_headers_include_auth_and_trid(self) -> None:
        adapter = _make_adapter()
        headers = adapter._headers("TTTC8434R", "token-abc")
        assert headers["authorization"] == "Bearer token-abc"
        assert headers["appkey"] == "app-key"
        assert headers["appsecret"] == "secret-key"
        assert headers["tr_id"] == "TTTC8434R"
        asyncio.run(adapter.close())

    def test_place_market_buy_order_maps_request(self) -> None:
        adapter = _make_adapter()
        adapter._ensure_token = AsyncMock(return_value="token-abc")
        adapter._client = MagicMock()
        adapter._client.post = AsyncMock(
            return_value=_mock_response({"output": {"ODNO": "A123"}})
        )

        result = asyncio.run(
            adapter.place_order(
                OrderRequest(
                    symbol="005930",
                    side="buy",
                    order_type="market",
                    qty=Decimal("3"),
                    price=None,
                )
            )
        )

        assert result.exchange_order_id == "A123"
        assert result.side == "buy"
        assert result.order_type == "market"
        assert result.requested_qty == Decimal("3")

        called_json = adapter._client.post.call_args.kwargs["json"]
        assert called_json["CANO"] == "12345678"
        assert called_json["PDNO"] == "005930"
        assert called_json["ORD_DVSN"] == "01"
        assert called_json["ORD_QTY"] == "3"
        assert called_json["ORD_UNPR"] == "0"
