"""거래소 계좌 API 엔드포인트 테스트.

커버리지 목표: 70%+
각 테스트는 독립적인 랜덤 사용자를 사용하여 데이터 격리를 보장합니다.
"""
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import UserCreate
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


# ── 공통 헬퍼 ─────────────────────────────────────────────────────────────────


def _user_and_headers(
    client: TestClient, db: Session
) -> tuple:
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
        "label": "My Test Account",
        "api_key": "test-api-key-123",
        "api_secret": "test-api-secret-456",
    }
    data.update(overrides)
    return data


# ── GET / ─────────────────────────────────────────────────────────────────────


class TestReadAccounts:
    def test_requires_auth(self, client: TestClient) -> None:
        r = client.get(f"{settings.API_V1_STR}/accounts/")
        assert r.status_code == 401

    def test_empty_list_for_new_user(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        r = client.get(f"{settings.API_V1_STR}/accounts/", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 0
        assert data["data"] == []

    def test_list_returns_created_accounts(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers,
            json=_account_payload(label="Account A"),
        )
        client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers,
            json=_account_payload(label="Account B"),
        )

        r = client.get(f"{settings.API_V1_STR}/accounts/", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        labels = {a["label"] for a in data["data"]}
        assert "Account A" in labels
        assert "Account B" in labels

    def test_other_user_accounts_not_visible(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers1 = _user_and_headers(client, db)
        _, headers2 = _user_and_headers(client, db)
        client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers1,
            json=_account_payload(),
        )

        r = client.get(f"{settings.API_V1_STR}/accounts/", headers=headers2)
        assert r.json()["count"] == 0

    def test_pagination_skip(self, client: TestClient, db: Session) -> None:
        _, headers = _user_and_headers(client, db)
        for i in range(3):
            client.post(
                f"{settings.API_V1_STR}/accounts/",
                headers=headers,
                json=_account_payload(label=f"Account {i}"),
            )

        r = client.get(
            f"{settings.API_V1_STR}/accounts/?skip=2", headers=headers
        )
        data = r.json()
        assert data["count"] == 1

    def test_pagination_limit(self, client: TestClient, db: Session) -> None:
        _, headers = _user_and_headers(client, db)
        for i in range(3):
            client.post(
                f"{settings.API_V1_STR}/accounts/",
                headers=headers,
                json=_account_payload(label=f"Account {i}"),
            )

        r = client.get(
            f"{settings.API_V1_STR}/accounts/?limit=2", headers=headers
        )
        data = r.json()
        assert data["count"] == 2


# ── GET /{id} ─────────────────────────────────────────────────────────────────


class TestReadAccountById:
    def test_get_account_by_id(self, client: TestClient, db: Session) -> None:
        _, headers = _user_and_headers(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers,
            json=_account_payload(),
        )
        account_id = create_r.json()["id"]

        r = client.get(
            f"{settings.API_V1_STR}/accounts/{account_id}", headers=headers
        )
        assert r.status_code == 200
        assert r.json()["id"] == account_id

    def test_not_found_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        r = client.get(
            f"{settings.API_V1_STR}/accounts/{uuid.uuid4()}",
            headers=headers,
        )
        assert r.status_code == 404

    def test_other_user_account_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers1 = _user_and_headers(client, db)
        _, headers2 = _user_and_headers(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers1,
            json=_account_payload(),
        )
        account_id = create_r.json()["id"]

        r = client.get(
            f"{settings.API_V1_STR}/accounts/{account_id}", headers=headers2
        )
        assert r.status_code == 404

    def test_requires_auth(self, client: TestClient) -> None:
        r = client.get(
            f"{settings.API_V1_STR}/accounts/{uuid.uuid4()}"
        )
        assert r.status_code == 401


# ── POST / ────────────────────────────────────────────────────────────────────


class TestCreateAccount:
    def test_create_account_returns_201(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        r = client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers,
            json=_account_payload(),
        )
        assert r.status_code == 201

    def test_create_account_response_schema(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        r = client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers,
            json=_account_payload(exchange="upbit", label="My Upbit"),
        )
        data = r.json()
        assert data["exchange"] == "upbit"
        assert data["label"] == "My Upbit"
        assert data["is_active"] is True
        assert data["is_valid"] is False
        assert "id" in data
        assert "created_at" in data

    def test_create_account_hides_api_keys(
        self, client: TestClient, db: Session
    ) -> None:
        """API 응답에 평문 키와 암호화값이 포함되지 않아야 함."""
        _, headers = _user_and_headers(client, db)
        r = client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers,
            json=_account_payload(api_key="my-secret-key"),
        )
        data = r.json()
        assert "api_key" not in data
        assert "api_secret" not in data
        assert "api_key_enc" not in data
        assert "api_secret_enc" not in data

    def test_create_account_with_extra_params(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        r = client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers,
            json=_account_payload(extra_params={"account_number": "12345"}),
        )
        assert r.status_code == 201

    def test_create_account_requires_auth(self, client: TestClient) -> None:
        r = client.post(
            f"{settings.API_V1_STR}/accounts/", json=_account_payload()
        )
        assert r.status_code == 401

    def test_create_account_invalid_exchange(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        r = client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers,
            json=_account_payload(exchange="invalid_exchange"),
        )
        assert r.status_code == 422

    def test_create_all_supported_exchanges(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        for exchange in ("binance", "upbit", "kis", "kiwoom"):
            r = client.post(
                f"{settings.API_V1_STR}/accounts/",
                headers=headers,
                json=_account_payload(exchange=exchange),
            )
            assert r.status_code == 201, f"{exchange} 계좌 생성 실패"
            assert r.json()["exchange"] == exchange


# ── PATCH /{id} ───────────────────────────────────────────────────────────────


class TestUpdateAccount:
    def test_update_label(self, client: TestClient, db: Session) -> None:
        _, headers = _user_and_headers(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers,
            json=_account_payload(label="Old Label"),
        )
        account_id = create_r.json()["id"]

        r = client.patch(
            f"{settings.API_V1_STR}/accounts/{account_id}",
            headers=headers,
            json={"label": "New Label"},
        )
        assert r.status_code == 200
        assert r.json()["label"] == "New Label"

    def test_update_is_active(self, client: TestClient, db: Session) -> None:
        _, headers = _user_and_headers(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers,
            json=_account_payload(),
        )
        account_id = create_r.json()["id"]

        r = client.patch(
            f"{settings.API_V1_STR}/accounts/{account_id}",
            headers=headers,
            json={"is_active": False},
        )
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    def test_update_not_found(self, client: TestClient, db: Session) -> None:
        _, headers = _user_and_headers(client, db)
        r = client.patch(
            f"{settings.API_V1_STR}/accounts/{uuid.uuid4()}",
            headers=headers,
            json={"label": "New Label"},
        )
        assert r.status_code == 404

    def test_update_other_user_account_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers1 = _user_and_headers(client, db)
        _, headers2 = _user_and_headers(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers1,
            json=_account_payload(),
        )
        account_id = create_r.json()["id"]

        r = client.patch(
            f"{settings.API_V1_STR}/accounts/{account_id}",
            headers=headers2,
            json={"label": "Hacked Label"},
        )
        assert r.status_code == 404

    def test_partial_update_does_not_change_other_fields(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers,
            json=_account_payload(label="Original", exchange="binance"),
        )
        account_id = create_r.json()["id"]

        client.patch(
            f"{settings.API_V1_STR}/accounts/{account_id}",
            headers=headers,
            json={"is_active": False},
        )

        r = client.get(
            f"{settings.API_V1_STR}/accounts/{account_id}", headers=headers
        )
        data = r.json()
        assert data["label"] == "Original"
        assert data["exchange"] == "binance"
        assert data["is_active"] is False


# ── DELETE /{id} ──────────────────────────────────────────────────────────────


class TestDeleteAccount:
    def test_delete_account_returns_200(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers,
            json=_account_payload(),
        )
        account_id = create_r.json()["id"]

        r = client.delete(
            f"{settings.API_V1_STR}/accounts/{account_id}", headers=headers
        )
        assert r.status_code == 200
        assert r.json()["message"] == "Exchange account deleted successfully"

    def test_deleted_account_not_found_by_id(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers,
            json=_account_payload(),
        )
        account_id = create_r.json()["id"]

        client.delete(
            f"{settings.API_V1_STR}/accounts/{account_id}", headers=headers
        )

        r = client.get(
            f"{settings.API_V1_STR}/accounts/{account_id}", headers=headers
        )
        assert r.status_code == 404

    def test_deleted_account_not_in_list(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers,
            json=_account_payload(),
        )
        account_id = create_r.json()["id"]

        client.delete(
            f"{settings.API_V1_STR}/accounts/{account_id}", headers=headers
        )

        r = client.get(f"{settings.API_V1_STR}/accounts/", headers=headers)
        data = r.json()
        assert data["count"] == 0
        ids = [a["id"] for a in data["data"]]
        assert account_id not in ids

    def test_delete_not_found(self, client: TestClient, db: Session) -> None:
        _, headers = _user_and_headers(client, db)
        r = client.delete(
            f"{settings.API_V1_STR}/accounts/{uuid.uuid4()}",
            headers=headers,
        )
        assert r.status_code == 404

    def test_delete_other_user_account_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers1 = _user_and_headers(client, db)
        _, headers2 = _user_and_headers(client, db)
        create_r = client.post(
            f"{settings.API_V1_STR}/accounts/",
            headers=headers1,
            json=_account_payload(),
        )
        account_id = create_r.json()["id"]

        r = client.delete(
            f"{settings.API_V1_STR}/accounts/{account_id}", headers=headers2
        )
        assert r.status_code == 404

    def test_delete_requires_auth(self, client: TestClient) -> None:
        r = client.delete(
            f"{settings.API_V1_STR}/accounts/{uuid.uuid4()}"
        )
        assert r.status_code == 401
