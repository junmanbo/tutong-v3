from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import UserCreate
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


def _user_and_headers(client: TestClient, db: Session) -> tuple:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    headers = user_authentication_headers(client=client, email=email, password=password)
    return user, headers


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
