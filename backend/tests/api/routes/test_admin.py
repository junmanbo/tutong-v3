"""관리자 API 엔드포인트 테스트.

superuser만 접근 가능한 /admin/* 엔드포인트를 검증합니다.
"""
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import BotStatusEnum, UserCreate
from tests.utils.account import create_random_account, create_random_bot
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


def _superuser_headers(client: TestClient) -> dict:
    return user_authentication_headers(
        client=client,
        email=settings.FIRST_SUPERUSER,
        password=settings.FIRST_SUPERUSER_PASSWORD,
    )


def _create_user(db: Session) -> tuple:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    return user, email, password


# ── GET /admin/users ──────────────────────────────────────────────────────────


class TestAdminListUsers:
    def test_superuser_can_list_all_users(
        self, client: TestClient, db: Session
    ) -> None:
        headers = _superuser_headers(client)
        # 유저 1명 추가 생성
        _create_user(db)
        r = client.get(f"{settings.API_V1_STR}/admin/users", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "count" in data
        assert data["count"] >= 1

    def test_normal_user_cannot_access(
        self, client: TestClient, db: Session
    ) -> None:
        user, email, password = _create_user(db)
        headers = user_authentication_headers(
            client=client, email=email, password=password
        )
        r = client.get(f"{settings.API_V1_STR}/admin/users", headers=headers)
        assert r.status_code == 403

    def test_requires_auth(self, client: TestClient) -> None:
        r = client.get(f"{settings.API_V1_STR}/admin/users")
        assert r.status_code == 401

    def test_pagination(self, client: TestClient, db: Session) -> None:
        headers = _superuser_headers(client)
        r = client.get(
            f"{settings.API_V1_STR}/admin/users",
            headers=headers,
            params={"skip": 0, "limit": 1},
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) <= 1


# ── GET /admin/users/{user_id} ────────────────────────────────────────────────


class TestAdminGetUser:
    def test_get_existing_user(self, client: TestClient, db: Session) -> None:
        headers = _superuser_headers(client)
        user, _, _ = _create_user(db)
        r = client.get(
            f"{settings.API_V1_STR}/admin/users/{user.id}", headers=headers
        )
        assert r.status_code == 200
        assert r.json()["id"] == str(user.id)
        assert r.json()["email"] == user.email

    def test_get_nonexistent_user_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        headers = _superuser_headers(client)
        r = client.get(
            f"{settings.API_V1_STR}/admin/users/{uuid.uuid4()}", headers=headers
        )
        assert r.status_code == 404

    def test_normal_user_cannot_access(
        self, client: TestClient, db: Session
    ) -> None:
        user, email, password = _create_user(db)
        headers = user_authentication_headers(
            client=client, email=email, password=password
        )
        r = client.get(
            f"{settings.API_V1_STR}/admin/users/{user.id}", headers=headers
        )
        assert r.status_code == 403


# ── PATCH /admin/users/{user_id}/deactivate ───────────────────────────────────


class TestAdminDeactivateUser:
    def test_deactivate_user(self, client: TestClient, db: Session) -> None:
        headers = _superuser_headers(client)
        user, _, _ = _create_user(db)
        assert user.is_active is True

        r = client.patch(
            f"{settings.API_V1_STR}/admin/users/{user.id}/deactivate",
            headers=headers,
        )
        assert r.status_code == 200
        assert "deactivated" in r.json()["message"]

        # DB에서 직접 확인
        db.refresh(user)
        assert user.is_active is False

    def test_deactivate_nonexistent_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        headers = _superuser_headers(client)
        r = client.patch(
            f"{settings.API_V1_STR}/admin/users/{uuid.uuid4()}/deactivate",
            headers=headers,
        )
        assert r.status_code == 404

    def test_normal_user_cannot_deactivate(
        self, client: TestClient, db: Session
    ) -> None:
        user, email, password = _create_user(db)
        headers = user_authentication_headers(
            client=client, email=email, password=password
        )
        r = client.patch(
            f"{settings.API_V1_STR}/admin/users/{user.id}/deactivate",
            headers=headers,
        )
        assert r.status_code == 403


# ── PATCH /admin/users/{user_id}/activate ─────────────────────────────────────


class TestAdminActivateUser:
    def test_activate_deactivated_user(
        self, client: TestClient, db: Session
    ) -> None:
        headers = _superuser_headers(client)
        user, _, _ = _create_user(db)

        # 먼저 비활성화
        user.is_active = False
        db.add(user)
        db.commit()

        r = client.patch(
            f"{settings.API_V1_STR}/admin/users/{user.id}/activate",
            headers=headers,
        )
        assert r.status_code == 200
        assert "activated" in r.json()["message"]

        db.refresh(user)
        assert user.is_active is True

    def test_activate_nonexistent_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        headers = _superuser_headers(client)
        r = client.patch(
            f"{settings.API_V1_STR}/admin/users/{uuid.uuid4()}/activate",
            headers=headers,
        )
        assert r.status_code == 404


# ── GET /admin/bots ───────────────────────────────────────────────────────────


class TestAdminListBots:
    def test_superuser_can_list_all_bots(
        self, client: TestClient, db: Session
    ) -> None:
        headers = _superuser_headers(client)
        # 일반 유저 봇 생성
        user, _, _ = _create_user(db)
        account = create_random_account(db, user.id)
        create_random_bot(db, user.id, account.id)

        r = client.get(f"{settings.API_V1_STR}/admin/bots", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "count" in data
        assert data["count"] >= 1

    def test_response_contains_bot_fields(
        self, client: TestClient, db: Session
    ) -> None:
        headers = _superuser_headers(client)
        user, _, _ = _create_user(db)
        account = create_random_account(db, user.id)
        create_random_bot(db, user.id, account.id)

        r = client.get(f"{settings.API_V1_STR}/admin/bots", headers=headers)
        bots = r.json()["data"]
        if bots:
            bot = bots[0]
            assert "id" in bot
            assert "name" in bot
            assert "status" in bot
            assert "bot_type" in bot

    def test_normal_user_cannot_access(
        self, client: TestClient, db: Session
    ) -> None:
        user, email, password = _create_user(db)
        headers = user_authentication_headers(
            client=client, email=email, password=password
        )
        r = client.get(f"{settings.API_V1_STR}/admin/bots", headers=headers)
        assert r.status_code == 403

    def test_requires_auth(self, client: TestClient) -> None:
        r = client.get(f"{settings.API_V1_STR}/admin/bots")
        assert r.status_code == 401
