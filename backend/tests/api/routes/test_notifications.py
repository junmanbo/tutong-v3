import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import Notification, UserCreate
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


def _user_and_headers(client: TestClient, db: Session) -> tuple:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    headers = user_authentication_headers(client=client, email=email, password=password)
    return user, headers


def _create_notification(
    db: Session,
    user_id: uuid.UUID,
    event_type: str = "bot_started",
    title: str = "Test",
    body: str = "Test body",
    is_read: bool = False,
) -> Notification:
    notif = Notification(
        user_id=user_id,
        event_type=event_type,
        title=title,
        body=body,
        is_read=is_read,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


class TestNotificationSettingsApi:
    def test_read_settings_creates_default_row(
        self, client: TestClient, db: Session
    ) -> None:
        user, headers = _user_and_headers(client, db)
        r = client.get(f"{settings.API_V1_STR}/notifications/settings", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == str(user.id)
        assert data["email_enabled"] is True
        assert data["notify_bot_start"] is True
        assert data["notify_account_error"] is True

    def test_update_settings(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        r = client.patch(
            f"{settings.API_V1_STR}/notifications/settings",
            headers=headers,
            json={
                "email_enabled": False,
                "notify_bot_start": False,
                "notify_take_profit": False,
                "telegram_enabled": True,
                "telegram_chat_id": "my-chat-id",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["email_enabled"] is False
        assert data["notify_bot_start"] is False
        assert data["notify_take_profit"] is False
        assert data["telegram_enabled"] is True
        assert data["telegram_chat_id"] == "my-chat-id"

    def test_requires_auth(self, client: TestClient) -> None:
        r = client.get(f"{settings.API_V1_STR}/notifications/settings")
        assert r.status_code == 401


# ── GET /notifications/ ───────────────────────────────────────────────────────


class TestReadNotifications:
    def test_empty_list_for_new_user(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        r = client.get(f"{settings.API_V1_STR}/notifications/", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 0
        assert data["data"] == []

    def test_returns_own_notifications_only(
        self, client: TestClient, db: Session
    ) -> None:
        user1, headers1 = _user_and_headers(client, db)
        user2, headers2 = _user_and_headers(client, db)
        _create_notification(db, user1.id, title="User1 Notif")
        _create_notification(db, user2.id, title="User2 Notif")

        r1 = client.get(f"{settings.API_V1_STR}/notifications/", headers=headers1)
        r2 = client.get(f"{settings.API_V1_STR}/notifications/", headers=headers2)
        assert r1.json()["count"] == 1
        assert r2.json()["count"] == 1
        assert r1.json()["data"][0]["title"] == "User1 Notif"
        assert r2.json()["data"][0]["title"] == "User2 Notif"

    def test_latest_first_ordering(
        self, client: TestClient, db: Session
    ) -> None:
        user, headers = _user_and_headers(client, db)
        _create_notification(db, user.id, title="First")
        _create_notification(db, user.id, title="Second")

        r = client.get(f"{settings.API_V1_STR}/notifications/", headers=headers)
        data = r.json()["data"]
        assert data[0]["title"] == "Second"
        assert data[1]["title"] == "First"

    def test_unread_only_filter(
        self, client: TestClient, db: Session
    ) -> None:
        user, headers = _user_and_headers(client, db)
        _create_notification(db, user.id, title="Unread", is_read=False)
        _create_notification(db, user.id, title="Read", is_read=True)

        r = client.get(
            f"{settings.API_V1_STR}/notifications/",
            headers=headers,
            params={"unread_only": True},
        )
        data = r.json()
        assert data["count"] == 1
        assert data["data"][0]["title"] == "Unread"

    def test_response_schema(self, client: TestClient, db: Session) -> None:
        user, headers = _user_and_headers(client, db)
        _create_notification(db, user.id)

        r = client.get(f"{settings.API_V1_STR}/notifications/", headers=headers)
        notif = r.json()["data"][0]
        assert "id" in notif
        assert "title" in notif
        assert "body" in notif
        assert "is_read" in notif
        assert "event_type" in notif
        assert "created_at" in notif

    def test_requires_auth(self, client: TestClient) -> None:
        r = client.get(f"{settings.API_V1_STR}/notifications/")
        assert r.status_code == 401


# ── POST /notifications/{id}/read ────────────────────────────────────────────


class TestMarkNotificationAsRead:
    def test_mark_notification_as_read(
        self, client: TestClient, db: Session
    ) -> None:
        user, headers = _user_and_headers(client, db)
        notif = _create_notification(db, user.id, is_read=False)

        r = client.post(
            f"{settings.API_V1_STR}/notifications/{notif.id}/read",
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["is_read"] is True

        db.refresh(notif)
        assert notif.is_read is True

    def test_mark_already_read_is_idempotent(
        self, client: TestClient, db: Session
    ) -> None:
        user, headers = _user_and_headers(client, db)
        notif = _create_notification(db, user.id, is_read=True)

        r = client.post(
            f"{settings.API_V1_STR}/notifications/{notif.id}/read",
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["is_read"] is True

    def test_nonexistent_notification_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        r = client.post(
            f"{settings.API_V1_STR}/notifications/{uuid.uuid4()}/read",
            headers=headers,
        )
        assert r.status_code == 404

    def test_other_user_notification_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        user1, _ = _user_and_headers(client, db)
        _, headers2 = _user_and_headers(client, db)
        notif = _create_notification(db, user1.id)

        r = client.post(
            f"{settings.API_V1_STR}/notifications/{notif.id}/read",
            headers=headers2,
        )
        assert r.status_code == 404

    def test_requires_auth(self, client: TestClient) -> None:
        r = client.post(
            f"{settings.API_V1_STR}/notifications/{uuid.uuid4()}/read"
        )
        assert r.status_code == 401


# ── POST /notifications/read-all ─────────────────────────────────────────────


class TestMarkAllNotificationsRead:
    def test_mark_all_as_read(self, client: TestClient, db: Session) -> None:
        user, headers = _user_and_headers(client, db)
        _create_notification(db, user.id, title="N1", is_read=False)
        _create_notification(db, user.id, title="N2", is_read=False)
        _create_notification(db, user.id, title="N3", is_read=True)

        r = client.post(
            f"{settings.API_V1_STR}/notifications/read-all", headers=headers
        )
        assert r.status_code == 200

        # 전체 조회 시 모두 읽음 처리 확인
        r2 = client.get(
            f"{settings.API_V1_STR}/notifications/",
            headers=headers,
            params={"unread_only": True},
        )
        assert r2.json()["count"] == 0

    def test_no_notifications_is_ok(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        r = client.post(
            f"{settings.API_V1_STR}/notifications/read-all", headers=headers
        )
        assert r.status_code == 200

    def test_only_affects_own_notifications(
        self, client: TestClient, db: Session
    ) -> None:
        user1, headers1 = _user_and_headers(client, db)
        user2, headers2 = _user_and_headers(client, db)
        _create_notification(db, user1.id, is_read=False)
        _create_notification(db, user2.id, is_read=False)

        # user1이 전체 읽음 처리
        client.post(
            f"{settings.API_V1_STR}/notifications/read-all", headers=headers1
        )

        # user2의 알림은 여전히 안읽음
        r2 = client.get(
            f"{settings.API_V1_STR}/notifications/",
            headers=headers2,
            params={"unread_only": True},
        )
        assert r2.json()["count"] == 1

    def test_requires_auth(self, client: TestClient) -> None:
        r = client.post(f"{settings.API_V1_STR}/notifications/read-all")
        assert r.status_code == 401
