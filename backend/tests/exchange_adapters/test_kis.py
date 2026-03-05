from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.exchange_adapters.kis import KisAdapter, _parse_kis_balance

UTC = timezone.utc


def _mock_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = payload
    return resp


def _make_adapter() -> KisAdapter:
    return KisAdapter(
        app_key="app-key",
        app_secret="app-secret",
        cano="12345678",
        acnt_prdt_cd="01",
        is_mock=True,
    )


class TestParseKisBalance:
    def test_parse_balance_filters_zero_qty_and_adds_krw(self) -> None:
        raw = {
            "output1": [
                {"pdno": "005930", "hldg_qty": "10", "ord_psbl_qty": "7"},
                {"pdno": "000660", "hldg_qty": "0", "ord_psbl_qty": "0"},
            ],
            "output2": [{"prvs_rcdv_amt": "500000"}],
        }
        balances = _parse_kis_balance(raw)

        assert len(balances) == 2
        stock = next(b for b in balances if b.asset == "005930")
        krw = next(b for b in balances if b.asset == "KRW")
        assert stock.free == Decimal("7")
        assert stock.locked == Decimal("3")
        assert krw.free == Decimal("500000")
        assert krw.locked == Decimal("0")


class TestTokenFlow:
    def test_ensure_token_refreshes_when_missing(self) -> None:
        adapter = _make_adapter()
        adapter._client = MagicMock()
        adapter._client.post = AsyncMock(
            return_value=_mock_response(
                {"access_token": "token-1", "expires_in": 3600}
            )
        )

        token = asyncio.run(adapter._ensure_token())
        assert token == "token-1"
        assert adapter._access_token == "token-1"
        assert adapter._token_expires_at is not None

    def test_ensure_token_reuses_valid_token(self) -> None:
        adapter = _make_adapter()
        adapter._access_token = "cached-token"
        adapter._token_expires_at = datetime.now(UTC) + timedelta(hours=1)
        adapter._refresh_token = AsyncMock()

        token = asyncio.run(adapter._ensure_token())
        assert token == "cached-token"
        adapter._refresh_token.assert_not_called()


class TestKisAdapterMethods:
    def test_get_balance_parses_response(self) -> None:
        adapter = _make_adapter()
        adapter._ensure_token = AsyncMock(return_value="token-abc")
        adapter._client = MagicMock()
        adapter._client.get = AsyncMock(
            return_value=_mock_response(
                {
                    "output1": [
                        {"pdno": "005930", "hldg_qty": "10", "ord_psbl_qty": "8"}
                    ],
                    "output2": [{"prvs_rcdv_amt": "100000"}],
                }
            )
        )

        balances = asyncio.run(adapter.get_balance())

        assert {b.asset for b in balances} == {"005930", "KRW"}
        adapter._client.get.assert_called_once()
        called_url = adapter._client.get.call_args.args[0]
        assert called_url.endswith("/uapi/domestic-stock/v1/trading/inquire-balance")

    def test_get_ticker_maps_fields_to_decimal(self) -> None:
        adapter = _make_adapter()
        adapter._ensure_token = AsyncMock(return_value="token-abc")
        adapter._client = MagicMock()
        adapter._client.get = AsyncMock(
            return_value=_mock_response(
                {
                    "output": {
                        "stck_prpr": "70200",
                        "bidp": "70100",
                        "askp": "70300",
                    }
                }
            )
        )

        ticker = asyncio.run(adapter.get_ticker("005930"))
        assert ticker.symbol == "005930"
        assert ticker.price == Decimal("70200")
        assert ticker.bid == Decimal("70100")
        assert ticker.ask == Decimal("70300")

    def test_place_order_returns_order_response(self) -> None:
        adapter = _make_adapter()
        adapter._ensure_token = AsyncMock(return_value="token-abc")
        adapter._client = MagicMock()
        adapter._client.post = AsyncMock(
            return_value=_mock_response({"output": {"ODNO": "A123456"}})
        )

        from app.exchange_adapters.base import OrderRequest

        result = asyncio.run(
            adapter.place_order(
            OrderRequest(
                symbol="005930",
                side="buy",
                order_type="limit",
                qty=Decimal("3"),
                price=Decimal("70000"),
            )
            )
        )

        assert result.exchange_order_id == "A123456"
        assert result.symbol == "005930"
        assert result.side == "buy"
        assert result.status == "open"
        assert result.filled_qty == Decimal("0")

    def test_validate_credentials_true_and_false(self) -> None:
        ok_adapter = _make_adapter()
        ok_adapter._ensure_token = AsyncMock(return_value="token-abc")
        ok_adapter.close = AsyncMock()

        assert asyncio.run(ok_adapter.validate_credentials()) is True
        ok_adapter.close.assert_awaited_once()

        bad_adapter = _make_adapter()
        bad_adapter._ensure_token = AsyncMock(side_effect=RuntimeError("bad key"))
        bad_adapter.close = AsyncMock()

        assert asyncio.run(bad_adapter.validate_credentials()) is False
        bad_adapter.close.assert_awaited_once()
