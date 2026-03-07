from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.exchange_adapters.kis import KisAdapter, _parse_kis_balance

UTC = timezone.utc


def _mock_response(payload: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.text = str(payload)
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
    def setup_method(self) -> None:
        KisAdapter._process_token_cache.clear()
        KisAdapter._token_locks.clear()
        KisAdapter._redis_client = None

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

    def test_refresh_token_retries_once_on_egw00133(self) -> None:
        adapter = _make_adapter()
        adapter._client = MagicMock()
        adapter._client.post = AsyncMock(
            side_effect=[
                _mock_response(
                    {
                        "error_code": "EGW00133",
                        "error_description": "접근토큰 발급 잠시 후 다시 시도하세요(1분당 1회)",
                    },
                    status_code=403,
                ),
                _mock_response({"access_token": "token-2", "expires_in": 3600}),
            ]
        )

        token = asyncio.run(adapter._ensure_token())
        assert token == "token-2"
        assert adapter._client.post.await_count == 2

    def test_token_shared_from_process_cache_across_instances(self) -> None:
        adapter1 = _make_adapter()
        adapter1._client = MagicMock()
        adapter1._client.post = AsyncMock(
            return_value=_mock_response({"access_token": "token-shared", "expires_in": 3600})
        )

        token1 = asyncio.run(adapter1._ensure_token())
        assert token1 == "token-shared"

        adapter2 = _make_adapter()
        adapter2._client = MagicMock()
        adapter2._client.post = AsyncMock(
            return_value=_mock_response({"access_token": "should-not-be-used", "expires_in": 3600})
        )

        token2 = asyncio.run(adapter2._ensure_token())
        assert token2 == "token-shared"
        adapter2._client.post.assert_not_called()


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


def _make_fake_ws(messages: list[str]):
    """async context manager + async iterable로 동작하는 WebSocket mock."""

    class FakeWS:
        def __init__(self, msgs: list[str]) -> None:
            self._msgs = msgs
            self.sent: list[str] = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def __aiter__(self):
            return self._gen()

        async def _gen(self):
            for msg in self._msgs:
                yield msg

        async def send(self, data: str) -> None:
            self.sent.append(data)

    return FakeWS(messages)


class TestKisOrderUpdateStream:
    """order_update_stream WebSocket 파싱 로직 테스트 (Mock WebSocket)."""

    @staticmethod
    def _h0stcni0_msg(
        odno: str = "A123",
        pdno: str = "005930",
        dvsn: str = "02",
        cntg_qty: str = "5",
        cntg_price: str = "70000",
        cntg_yn: str = "Y",
        ord_qty: str = "10",
    ) -> str:
        """H0STCNI0 체결통보 메시지 형식 생성.
        fields[0..14]: 계좌, 상품코드, 주문번호, 원주문번호, 주문구분명,
                       종목코드, 매매구분(01매도/02매수), 체결수량, 체결단가,
                       체결시각, 거부여부, 체결여부(Y/N), 접수여부, 지점번호, 주문수량
        """
        fields = [
            "12345678", "01", odno, "", "시장가매수",
            pdno, dvsn, cntg_qty, cntg_price, "091500",
            "N", cntg_yn, "1", "001", ord_qty,
        ]
        return "0|H0STCNI0|user123|" + "^".join(fields)

    def _make_adapter_with_ws_mock(self, messages: list[str]):
        from unittest.mock import AsyncMock, MagicMock, patch
        adapter = _make_adapter()
        adapter._ensure_token = AsyncMock(return_value="token")
        adapter._client = MagicMock()
        adapter._client.post = AsyncMock(
            return_value=_mock_response({"approval_key": "ws-key"})
        )
        return adapter

    def test_filled_message_parses_to_closed_order(self) -> None:
        from unittest.mock import patch

        msg = self._h0stcni0_msg(
            odno="B999", pdno="005380", dvsn="02",
            cntg_qty="3", cntg_price="85000", cntg_yn="Y", ord_qty="3",
        )
        adapter = self._make_adapter_with_ws_mock([msg])
        fake_ws = _make_fake_ws([msg])

        async def _run():
            results = []
            with patch("websockets.connect", return_value=fake_ws):
                async for order in adapter.order_update_stream():
                    results.append(order)
                    break
            return results

        results = asyncio.run(_run())
        assert len(results) == 1
        order = results[0]
        assert order.exchange_order_id == "B999"
        assert order.symbol == "005380"
        assert order.side == "buy"
        assert order.status == "closed"
        assert order.filled_qty == Decimal("3")
        assert order.avg_fill_price == Decimal("85000")

    def test_pending_message_parses_to_open_order(self) -> None:
        from unittest.mock import patch

        msg = self._h0stcni0_msg(
            odno="C001", pdno="000660", dvsn="01",
            cntg_qty="0", cntg_price="0", cntg_yn="N", ord_qty="5",
        )
        adapter = self._make_adapter_with_ws_mock([msg])
        fake_ws = _make_fake_ws([msg])

        async def _run():
            results = []
            with patch("websockets.connect", return_value=fake_ws):
                async for order in adapter.order_update_stream():
                    results.append(order)
                    break
            return results

        results = asyncio.run(_run())
        assert len(results) == 1
        order = results[0]
        assert order.side == "sell"
        assert order.status == "open"
        assert order.avg_fill_price is None

    def test_non_h0stcni0_message_is_skipped(self) -> None:
        from unittest.mock import patch

        irrelevant = "0|H0STCNT0|user|005930^70000^..."
        valid = self._h0stcni0_msg(odno="D001")
        adapter = self._make_adapter_with_ws_mock([irrelevant, valid])
        fake_ws = _make_fake_ws([irrelevant, valid])

        async def _run():
            results = []
            with patch("websockets.connect", return_value=fake_ws):
                async for order in adapter.order_update_stream():
                    results.append(order)
                    break
            return results

        results = asyncio.run(_run())
        # irrelevant 메시지는 스킵, valid 메시지만 파싱
        assert len(results) == 1
        assert results[0].exchange_order_id == "D001"
