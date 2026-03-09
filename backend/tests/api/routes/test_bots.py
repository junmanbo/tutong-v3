"""봇 API 엔드포인트 테스트.

커버리지 목표: 70%+
각 테스트는 독립적인 랜덤 사용자를 사용하여 데이터 격리를 보장합니다.
Celery·Redis 외부 의존성은 mock으로 대체합니다.
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import BotStatusEnum, UserCreate
from tests.utils.account import create_random_account, create_random_bot
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string

# 계좌 등록 API에서 validate_credentials가 호출되므로,
# bot 테스트에서는 계좌를 DB 직접 생성 방식을 사용합니다.


# ── 공통 헬퍼 ─────────────────────────────────────────────────────────────────


def _user_and_headers(client: TestClient, db: Session) -> tuple:
    """랜덤 사용자를 생성하고 인증 헤더를 반환."""
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    headers = user_authentication_headers(
        client=client, email=email, password=password
    )
    return user, headers


def _account_payload(**overrides) -> dict:
    data: dict = {
        "exchange": "binance",
        "label": "Test Account",
        "api_key": "test-key",
        "api_secret": "test-secret",
    }
    data.update(overrides)
    return data


def _bot_payload(account_id: str, **overrides) -> dict:
    data: dict = {
        "name": "Test Bot",
        "bot_type": "spot_dca",
        "symbol": "BTC/USDT",
        "investment_amount": "100.0",
        "account_id": account_id,
    }
    data.update(overrides)
    return data


def _strategy_bot_payload(account_id: str, bot_type: str) -> dict:
    payload = _bot_payload(account_id, bot_type=bot_type)
    if bot_type == "spot_grid":
        payload["config"] = {
            "upper": "120000000",
            "lower": "90000000",
            "grid_count": 20,
            "arithmetic": True,
            "amount_per_grid": "50000",
        }
    elif bot_type == "position_snowball":
        payload["config"] = {
            "drop_pct": "5",
            "amount_per_buy": "100000",
            "take_profit_pct": "5",
            "max_buys": 5,
        }
    elif bot_type == "rebalancing":
        payload["symbol"] = None
        payload["base_currency"] = "BTC"
        payload["quote_currency"] = "KRW"
        payload["config"] = {
            "assets": {"BTC": "40", "ETH": "30", "KRW": "30"},
            "mode": "deviation",
            "threshold_pct": "5",
            "interval_seconds": 604800,
            "quote": "KRW",
        }
    elif bot_type == "spot_dca":
        payload["config"] = {
            "amount_per_order": "100000",
            "interval_seconds": 86400,
            "order_type": "market",
            "total_orders": 30,
        }
    elif bot_type == "algo_orders":
        payload["config"] = {
            "side": "buy",
            "total_qty": "0.1",
            "num_slices": 12,
            "duration_seconds": 3600,
            "order_type": "market",
        }
    return payload


def _setup_user_with_account(
    client: TestClient, db: Session
) -> tuple:
    """사용자와 거래소 계좌를 생성하고 반환.

    계좌는 DB 직접 생성 방식을 사용하여 거래소 API Key 검증을 우회합니다.
    계좌 등록 API 자체의 검증은 test_accounts.py에서 별도로 테스트합니다.
    """
    user, headers = _user_and_headers(client, db)
    account = create_random_account(db, user.id)
    return user, headers, str(account.id)


# ── GET / ─────────────────────────────────────────────────────────────────────


class TestReadBots:
    def test_requires_auth(self, client: TestClient) -> None:
        r = client.get(f"{settings.API_V1_STR}/bots/")
        assert r.status_code == 401

    def test_empty_list_for_new_user(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, _ = _setup_user_with_account(client, db)
        r = client.get(f"{settings.API_V1_STR}/bots/", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 0
        assert data["data"] == []

    def test_list_returns_created_bots(
        self, client: TestClient, db: Session
    ) -> None:
        """DB 직접 생성으로 플랜 한도 우회 후 목록 API 검증."""
        user, headers, account_id = _setup_user_with_account(client, db)
        # 플랜 한도 없이 DB에 직접 2개 생성
        create_random_bot(db, user.id, uuid.UUID(account_id))
        create_random_bot(db, user.id, uuid.UUID(account_id))

        r = client.get(f"{settings.API_V1_STR}/bots/", headers=headers)
        data = r.json()
        assert data["count"] == 2

    def test_other_user_bots_not_visible(
        self, client: TestClient, db: Session
    ) -> None:
        user1, headers1, account_id = _setup_user_with_account(client, db)
        _, headers2, _ = _setup_user_with_account(client, db)
        create_random_bot(db, user1.id, uuid.UUID(account_id))

        r = client.get(f"{settings.API_V1_STR}/bots/", headers=headers2)
        assert r.json()["count"] == 0

    def test_list_response_schema(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, account_id = _setup_user_with_account(client, db)
        client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id, name="My Bot"),
        )

        r = client.get(f"{settings.API_V1_STR}/bots/", headers=headers)
        bot = r.json()["data"][0]
        assert "id" in bot
        assert "name" in bot
        assert "status" in bot
        assert "bot_type" in bot
        assert "total_pnl" in bot
        assert "created_at" in bot


# ── GET /{id} ─────────────────────────────────────────────────────────────────


class TestReadBotById:
    def test_get_bot_by_id(self, client: TestClient, db: Session) -> None:
        _, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        r = client.get(
            f"{settings.API_V1_STR}/bots/{bot_id}", headers=headers
        )
        assert r.status_code == 200
        assert r.json()["id"] == bot_id

    def test_not_found_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, _ = _setup_user_with_account(client, db)
        r = client.get(
            f"{settings.API_V1_STR}/bots/{uuid.uuid4()}", headers=headers
        )
        assert r.status_code == 404

    def test_other_user_bot_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        user1, headers1, account_id = _setup_user_with_account(client, db)
        _, headers2, _ = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers1,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        r = client.get(
            f"{settings.API_V1_STR}/bots/{bot_id}", headers=headers2
        )
        assert r.status_code == 404

    def test_requires_auth(self, client: TestClient) -> None:
        r = client.get(f"{settings.API_V1_STR}/bots/{uuid.uuid4()}")
        assert r.status_code == 401


# ── POST / ────────────────────────────────────────────────────────────────────


class TestCreateBot:
    def test_create_bot_returns_201(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, account_id = _setup_user_with_account(client, db)
        r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        assert r.status_code == 201

    def test_create_bot_initial_status_stopped(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, account_id = _setup_user_with_account(client, db)
        r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        assert r.json()["status"] == "stopped"

    def test_create_bot_response_schema(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, account_id = _setup_user_with_account(client, db)
        r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(
                account_id, name="Grid Bot", bot_type="spot_grid"
            ),
        )
        data = r.json()
        assert data["name"] == "Grid Bot"
        assert data["bot_type"] == "spot_grid"
        assert "id" in data
        assert "created_at" in data
        assert "total_pnl" in data
        assert "total_pnl_pct" in data

    def test_create_bot_plan_limit_exceeded(
        self, client: TestClient, db: Session
    ) -> None:
        """Free 플랜 (봇 1개 한도) 초과 시 403."""
        _, headers, account_id = _setup_user_with_account(client, db)
        r1 = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id, name="Bot 1"),
        )
        assert r1.status_code == 201

        r2 = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id, name="Bot 2"),
        )
        assert r2.status_code == 403
        assert "Bot limit" in r2.json()["detail"]

    def test_create_bot_invalid_account_id(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, _ = _setup_user_with_account(client, db)
        r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(str(uuid.uuid4())),
        )
        assert r.status_code == 404

    def test_create_bot_with_other_user_account_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers1, account_id = _setup_user_with_account(client, db)
        _, headers2, _ = _setup_user_with_account(client, db)

        r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers2,
            json=_bot_payload(account_id),
        )
        assert r.status_code == 404

    def test_create_bot_requires_auth(self, client: TestClient) -> None:
        r = client.post(
            f"{settings.API_V1_STR}/bots/",
            json=_bot_payload("some-id"),
        )
        assert r.status_code == 401

    def test_create_all_bot_types(
        self, client: TestClient, db: Session
    ) -> None:
        """지원하는 모든 봇 타입으로 생성 가능한지 확인."""
        bot_types = [
            "spot_grid",
            "position_snowball",
            "rebalancing",
            "spot_dca",
            "algo_orders",
        ]
        for bot_type in bot_types:
            user, headers, account_id = _setup_user_with_account(client, db)
            r = client.post(
                f"{settings.API_V1_STR}/bots/",
                headers=headers,
                json=_bot_payload(account_id, bot_type=bot_type),
            )
            assert r.status_code == 201, f"{bot_type} 봇 생성 실패"
            assert r.json()["bot_type"] == bot_type


# ── PATCH /{id} ───────────────────────────────────────────────────────────────


class TestUpdateBot:
    def test_update_bot_name(self, client: TestClient, db: Session) -> None:
        _, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id, name="Old Name"),
        )
        bot_id = create_r.json()["id"]

        r = client.patch(
            f"{settings.API_V1_STR}/bots/{bot_id}",
            headers=headers,
            json={"name": "New Name"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "New Name"

    def test_update_bot_not_found(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, _ = _setup_user_with_account(client, db)
        r = client.patch(
            f"{settings.API_V1_STR}/bots/{uuid.uuid4()}",
            headers=headers,
            json={"name": "New Name"},
        )
        assert r.status_code == 404

    def test_update_running_bot_returns_409(
        self, client: TestClient, db: Session
    ) -> None:
        """실행 중인 봇은 수정 불가."""
        user, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        # DB에서 직접 running 상태로 변경
        bot = crud.get_bot(
            session=db, bot_id=uuid.UUID(bot_id), user_id=user.id
        )
        assert bot is not None
        bot.status = BotStatusEnum.running
        db.add(bot)
        db.commit()

        r = client.patch(
            f"{settings.API_V1_STR}/bots/{bot_id}",
            headers=headers,
            json={"name": "New Name"},
        )
        assert r.status_code == 409
        assert "stopped" in r.json()["detail"]

    def test_update_other_user_bot_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers1, account_id = _setup_user_with_account(client, db)
        _, headers2, _ = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers1,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        r = client.patch(
            f"{settings.API_V1_STR}/bots/{bot_id}",
            headers=headers2,
            json={"name": "Hacked"},
        )
        assert r.status_code == 404


# ── DELETE /{id} ──────────────────────────────────────────────────────────────


class TestDeleteBot:
    def test_delete_bot_returns_200(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        r = client.delete(
            f"{settings.API_V1_STR}/bots/{bot_id}", headers=headers
        )
        assert r.status_code == 200
        assert r.json()["message"] == "Bot deleted successfully"

    def test_deleted_bot_not_in_list(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        client.delete(
            f"{settings.API_V1_STR}/bots/{bot_id}", headers=headers
        )

        r = client.get(f"{settings.API_V1_STR}/bots/", headers=headers)
        ids = [b["id"] for b in r.json()["data"]]
        assert bot_id not in ids

    def test_delete_running_bot_returns_409(
        self, client: TestClient, db: Session
    ) -> None:
        user, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        bot = crud.get_bot(
            session=db, bot_id=uuid.UUID(bot_id), user_id=user.id
        )
        assert bot is not None
        bot.status = BotStatusEnum.running
        db.add(bot)
        db.commit()

        r = client.delete(
            f"{settings.API_V1_STR}/bots/{bot_id}", headers=headers
        )
        assert r.status_code == 409
        assert "stopped" in r.json()["detail"]

    def test_delete_not_found(self, client: TestClient, db: Session) -> None:
        _, headers, _ = _setup_user_with_account(client, db)
        r = client.delete(
            f"{settings.API_V1_STR}/bots/{uuid.uuid4()}", headers=headers
        )
        assert r.status_code == 404

    def test_delete_other_user_bot_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers1, account_id = _setup_user_with_account(client, db)
        _, headers2, _ = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers1,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        r = client.delete(
            f"{settings.API_V1_STR}/bots/{bot_id}", headers=headers2
        )
        assert r.status_code == 404


# ── POST /{id}/start ──────────────────────────────────────────────────────────


class TestStartBot:
    def test_start_bot_returns_pending(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        mock_celery = MagicMock()
        with patch("app.api.routes.bots.Celery", return_value=mock_celery):
            r = client.post(
                f"{settings.API_V1_STR}/bots/{bot_id}/start",
                headers=headers,
            )

        assert r.status_code == 200
        assert r.json()["status"] == "pending"

    def test_start_bot_dispatches_celery_task(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id, bot_type="spot_dca"),
        )
        bot_id = create_r.json()["id"]

        mock_celery = MagicMock()
        with patch("app.api.routes.bots.Celery", return_value=mock_celery):
            client.post(
                f"{settings.API_V1_STR}/bots/{bot_id}/start",
                headers=headers,
            )

        mock_celery.send_task.assert_called_once()
        call_args = mock_celery.send_task.call_args
        assert call_args[0][0] == "bot_engine.workers.spot_dca.run"
        assert call_args[1]["kwargs"]["bot_id"] == bot_id

    def test_start_bot_triggers_notification(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        mock_celery = MagicMock()
        with (
            patch("app.api.routes.bots.Celery", return_value=mock_celery),
            patch("app.api.routes.bots.queue_notification_event") as mock_notify,
        ):
            r = client.post(
                f"{settings.API_V1_STR}/bots/{bot_id}/start",
                headers=headers,
            )

        assert r.status_code == 200
        mock_notify.assert_called_once()

    def test_start_already_running_bot_returns_409(
        self, client: TestClient, db: Session
    ) -> None:
        user, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        bot = crud.get_bot(
            session=db, bot_id=uuid.UUID(bot_id), user_id=user.id
        )
        assert bot is not None
        bot.status = BotStatusEnum.running
        db.add(bot)
        db.commit()

        with patch("app.api.routes.bots.Celery"):
            r = client.post(
                f"{settings.API_V1_STR}/bots/{bot_id}/start",
                headers=headers,
            )
        assert r.status_code == 409

    def test_start_error_state_bot(
        self, client: TestClient, db: Session
    ) -> None:
        """error 상태 봇도 재시작 가능."""
        user, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        bot = crud.get_bot(
            session=db, bot_id=uuid.UUID(bot_id), user_id=user.id
        )
        assert bot is not None
        bot.status = BotStatusEnum.error
        db.add(bot)
        db.commit()

        mock_celery = MagicMock()
        with patch("app.api.routes.bots.Celery", return_value=mock_celery):
            r = client.post(
                f"{settings.API_V1_STR}/bots/{bot_id}/start",
                headers=headers,
            )
        assert r.status_code == 200

    def test_start_bot_not_found(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, _ = _setup_user_with_account(client, db)
        with patch("app.api.routes.bots.Celery"):
            r = client.post(
                f"{settings.API_V1_STR}/bots/{uuid.uuid4()}/start",
                headers=headers,
            )
        assert r.status_code == 404

    def test_start_pending_bot_returns_409(
        self, client: TestClient, db: Session
    ) -> None:
        """이미 pending 상태인 봇은 시작 불가."""
        user, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        bot = crud.get_bot(
            session=db, bot_id=uuid.UUID(bot_id), user_id=user.id
        )
        assert bot is not None
        bot.status = BotStatusEnum.pending
        db.add(bot)
        db.commit()

        with patch("app.api.routes.bots.Celery"):
            r = client.post(
                f"{settings.API_V1_STR}/bots/{bot_id}/start",
                headers=headers,
            )
        assert r.status_code == 409


# ── POST /{id}/stop ───────────────────────────────────────────────────────────


class TestStopBot:
    def test_stop_running_bot_returns_stopped(
        self, client: TestClient, db: Session
    ) -> None:
        user, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        bot = crud.get_bot(
            session=db, bot_id=uuid.UUID(bot_id), user_id=user.id
        )
        assert bot is not None
        bot.status = BotStatusEnum.running
        db.add(bot)
        db.commit()

        mock_redis = MagicMock()
        with patch("redis.from_url", return_value=mock_redis):
            r = client.post(
                f"{settings.API_V1_STR}/bots/{bot_id}/stop",
                headers=headers,
            )

        assert r.status_code == 200
        assert r.json()["status"] == "stopped"

    def test_stop_bot_sets_redis_signal(
        self, client: TestClient, db: Session
    ) -> None:
        """중지 시 Redis에 stop 신호를 설정해야 함."""
        user, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        bot = crud.get_bot(
            session=db, bot_id=uuid.UUID(bot_id), user_id=user.id
        )
        assert bot is not None
        bot.status = BotStatusEnum.running
        db.add(bot)
        db.commit()

        mock_redis = MagicMock()
        with patch("redis.from_url", return_value=mock_redis):
            client.post(
                f"{settings.API_V1_STR}/bots/{bot_id}/stop",
                headers=headers,
            )

        mock_redis.set.assert_called_once_with(f"bot:{bot_id}:stop", "1")

    def test_stop_bot_triggers_notification(
        self, client: TestClient, db: Session
    ) -> None:
        user, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        bot = crud.get_bot(
            session=db, bot_id=uuid.UUID(bot_id), user_id=user.id
        )
        assert bot is not None
        bot.status = BotStatusEnum.running
        db.add(bot)
        db.commit()

        mock_redis = MagicMock()
        with (
            patch("redis.from_url", return_value=mock_redis),
            patch("app.api.routes.bots.queue_notification_event") as mock_notify,
        ):
            r = client.post(
                f"{settings.API_V1_STR}/bots/{bot_id}/stop",
                headers=headers,
            )
        assert r.status_code == 200
        mock_notify.assert_called_once()

    def test_stop_pending_bot(
        self, client: TestClient, db: Session
    ) -> None:
        """pending 상태 봇도 중지 가능."""
        user, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        bot = crud.get_bot(
            session=db, bot_id=uuid.UUID(bot_id), user_id=user.id
        )
        assert bot is not None
        bot.status = BotStatusEnum.pending
        db.add(bot)
        db.commit()

        mock_redis = MagicMock()
        with patch("redis.from_url", return_value=mock_redis):
            r = client.post(
                f"{settings.API_V1_STR}/bots/{bot_id}/stop",
                headers=headers,
            )
        assert r.status_code == 200
        assert r.json()["status"] == "stopped"

    def test_stop_already_stopped_bot_returns_409(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        r = client.post(
            f"{settings.API_V1_STR}/bots/{bot_id}/stop", headers=headers
        )
        assert r.status_code == 409

    def test_stop_bot_not_found(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, _ = _setup_user_with_account(client, db)
        r = client.post(
            f"{settings.API_V1_STR}/bots/{uuid.uuid4()}/stop",
            headers=headers,
        )
        assert r.status_code == 404

    def test_stop_other_user_bot_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        user1, headers1, account_id = _setup_user_with_account(client, db)
        _, headers2, _ = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers1,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        r = client.post(
            f"{settings.API_V1_STR}/bots/{bot_id}/stop", headers=headers2
        )
        assert r.status_code == 404


class TestReadBotLogs:
    def test_read_bot_logs_empty(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = create_r.json()["id"]

        r = client.get(
            f"{settings.API_V1_STR}/bots/{bot_id}/logs",
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["count"] == 0
        assert r.json()["data"] == []

    def test_read_bot_logs_returns_latest_first(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers, account_id = _setup_user_with_account(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/bots/",
            headers=headers,
            json=_bot_payload(account_id),
        )
        bot_id = uuid.UUID(create_r.json()["id"])

        crud.create_bot_log(
            session=db,
            bot_id=bot_id,
            event_type="a",
            level="info",
            message="first",
        )
        crud.create_bot_log(
            session=db,
            bot_id=bot_id,
            event_type="b",
            level="warning",
            message="second",
        )

        r = client.get(
            f"{settings.API_V1_STR}/bots/{bot_id}/logs",
            headers=headers,
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 2
        assert data[0]["message"] == "second"
        assert data[1]["message"] == "first"

        # ownership check (different user cannot read)
        _, headers_other, _ = _setup_user_with_account(client, db)
        r_other = client.get(
            f"{settings.API_V1_STR}/bots/{bot_id}/logs",
            headers=headers_other,
        )
        assert r_other.status_code == 404


@pytest.mark.parametrize(
    ("bot_type", "expected_task"),
    [
        ("spot_grid", "bot_engine.workers.spot_grid.run"),
        ("position_snowball", "bot_engine.workers.snowball.run"),
        ("rebalancing", "bot_engine.workers.rebalancing.run"),
        ("spot_dca", "bot_engine.workers.spot_dca.run"),
        ("algo_orders", "bot_engine.workers.algo_orders.run"),
    ],
)
def test_strategy_start_dispatch_mapping_integration(
    client: TestClient,
    db: Session,
    bot_type: str,
    expected_task: str,
) -> None:
    """5개 전략별 시작 요청이 올바른 worker task로 매핑되는지 검증."""
    _, headers, account_id = _setup_user_with_account(client, db)
    create_r = client.post(
        f"{settings.API_V1_STR}/bots/",
        headers=headers,
        json=_strategy_bot_payload(account_id, bot_type),
    )
    assert create_r.status_code == 201
    bot_id = create_r.json()["id"]

    mock_celery = MagicMock()
    with patch("app.api.routes.bots.Celery", return_value=mock_celery):
        start_r = client.post(
            f"{settings.API_V1_STR}/bots/{bot_id}/start",
            headers=headers,
        )

    assert start_r.status_code == 200
    assert start_r.json()["status"] == "pending"
    mock_celery.send_task.assert_called_once()
    assert mock_celery.send_task.call_args[0][0] == expected_task
    assert mock_celery.send_task.call_args[1]["kwargs"]["bot_id"] == bot_id


@pytest.mark.parametrize(
    "bot_type",
    ["spot_grid", "position_snowball", "rebalancing", "spot_dca", "algo_orders"],
)
def test_strategy_stop_from_pending_integration(
    client: TestClient,
    db: Session,
    bot_type: str,
) -> None:
    """5개 전략 모두 pending 상태에서 stop 요청이 정상 동작해야 한다."""
    _, headers, account_id = _setup_user_with_account(client, db)
    create_r = client.post(
        f"{settings.API_V1_STR}/bots/",
        headers=headers,
        json=_strategy_bot_payload(account_id, bot_type),
    )
    assert create_r.status_code == 201
    bot_id = create_r.json()["id"]

    mock_celery = MagicMock()
    with patch("app.api.routes.bots.Celery", return_value=mock_celery):
        start_r = client.post(
            f"{settings.API_V1_STR}/bots/{bot_id}/start",
            headers=headers,
        )
    assert start_r.status_code == 200
    assert start_r.json()["status"] == "pending"

    mock_redis = MagicMock()
    with patch("redis.from_url", return_value=mock_redis):
        stop_r = client.post(
            f"{settings.API_V1_STR}/bots/{bot_id}/stop",
            headers=headers,
        )
    assert stop_r.status_code == 200
    assert stop_r.json()["status"] == "stopped"
    mock_redis.set.assert_called_once_with(f"bot:{bot_id}:stop", "1")
