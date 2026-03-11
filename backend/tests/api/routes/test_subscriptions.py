"""구독/결제 API 엔드포인트 테스트.

/subscriptions/* 엔드포인트를 검증합니다.
PG 연동 없이 플랜 조회 및 구독 현황을 테스트합니다.
"""
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import (
    PaymentHistory,
    SubscriptionPlan,
    SubscriptionStatusEnum,
    UserCreate,
    UserSubscription,
)
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string

UTC = timezone.utc


def _user_and_headers(client: TestClient, db: Session) -> tuple:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    headers = user_authentication_headers(
        client=client, email=email, password=password
    )
    return user, headers


def _create_plan(db: Session, name: str | None = None) -> SubscriptionPlan:
    if name is None:
        name = f"plan_{random_lower_string()}"
    plan = SubscriptionPlan(
        name=name,
        display_name=name.capitalize(),
        price_krw=9900,
        max_bots=5,
        max_accounts=5,
        features={"support": "email"},
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _create_subscription(
    db: Session, user_id: uuid.UUID, plan_id: uuid.UUID
) -> UserSubscription:
    sub = UserSubscription(
        user_id=user_id,
        plan_id=plan_id,
        status=SubscriptionStatusEnum.active,
        started_at=datetime.now(UTC),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


# ── GET /subscriptions/plans ──────────────────────────────────────────────────


class TestListPlans:
    def test_list_active_plans(self, client: TestClient, db: Session) -> None:
        _create_plan(db)
        r = client.get(f"{settings.API_V1_STR}/subscriptions/plans")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # 활성 플랜만 포함되어야 함
        assert all(p["is_active"] for p in data)

    def test_inactive_plan_not_listed(
        self, client: TestClient, db: Session
    ) -> None:
        plan = _create_plan(db, f"inactive_{random_lower_string()}")
        plan.is_active = False
        db.add(plan)
        db.commit()

        r = client.get(f"{settings.API_V1_STR}/subscriptions/plans")
        plan_ids = [p["id"] for p in r.json()]
        assert str(plan.id) not in plan_ids

    def test_plan_response_schema(
        self, client: TestClient, db: Session
    ) -> None:
        created = _create_plan(db)
        r = client.get(f"{settings.API_V1_STR}/subscriptions/plans")
        assert r.status_code == 200
        plans = r.json()
        plan = next((p for p in plans if p["id"] == str(created.id)), None)
        if plan:
            assert "id" in plan
            assert "name" in plan
            assert "display_name" in plan
            assert "price_krw" in plan
            assert "max_bots" in plan
            assert "max_accounts" in plan
            assert "features" in plan
            assert "is_active" in plan

    def test_no_auth_required(self, client: TestClient) -> None:
        """플랜 목록은 인증 없이 조회 가능해야 함."""
        r = client.get(f"{settings.API_V1_STR}/subscriptions/plans")
        assert r.status_code == 200


# ── GET /subscriptions/plans/{plan_id} ────────────────────────────────────────


class TestGetPlan:
    def test_get_plan_by_name(self, client: TestClient, db: Session) -> None:
        unique_name = f"plan_{random_lower_string()}"
        plan = _create_plan(db, unique_name)
        r = client.get(
            f"{settings.API_V1_STR}/subscriptions/plans/{unique_name}"
        )
        assert r.status_code == 200
        assert r.json()["id"] == str(plan.id)

    def test_get_plan_by_id(self, client: TestClient, db: Session) -> None:
        plan = _create_plan(db, f"plan_{random_lower_string()}")
        r = client.get(
            f"{settings.API_V1_STR}/subscriptions/plans/{plan.id}"
        )
        assert r.status_code == 200
        assert r.json()["id"] == str(plan.id)

    def test_nonexistent_plan_returns_404(self, client: TestClient) -> None:
        r = client.get(
            f"{settings.API_V1_STR}/subscriptions/plans/nonexistent-plan"
        )
        assert r.status_code == 404

    def test_nonexistent_uuid_returns_404(self, client: TestClient) -> None:
        r = client.get(
            f"{settings.API_V1_STR}/subscriptions/plans/{uuid.uuid4()}"
        )
        assert r.status_code == 404


# ── GET /subscriptions/me ─────────────────────────────────────────────────────


class TestGetMySubscription:
    def test_returns_null_when_no_subscription(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        r = client.get(
            f"{settings.API_V1_STR}/subscriptions/me", headers=headers
        )
        assert r.status_code == 200
        assert r.json() is None

    def test_returns_active_subscription(
        self, client: TestClient, db: Session
    ) -> None:
        user, headers = _user_and_headers(client, db)
        plan = _create_plan(db, f"plan_{random_lower_string()}")
        sub = _create_subscription(db, user.id, plan.id)

        r = client.get(
            f"{settings.API_V1_STR}/subscriptions/me", headers=headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data is not None
        assert data["id"] == str(sub.id)
        assert data["status"] == "active"
        assert data["plan_id"] == str(plan.id)

    def test_requires_auth(self, client: TestClient) -> None:
        r = client.get(f"{settings.API_V1_STR}/subscriptions/me")
        assert r.status_code == 401

    def test_response_schema(self, client: TestClient, db: Session) -> None:
        user, headers = _user_and_headers(client, db)
        plan = _create_plan(db, f"plan_{random_lower_string()}")
        _create_subscription(db, user.id, plan.id)

        r = client.get(
            f"{settings.API_V1_STR}/subscriptions/me", headers=headers
        )
        data = r.json()
        assert "id" in data
        assert "user_id" in data
        assert "plan_id" in data
        assert "status" in data
        assert "started_at" in data


# ── DELETE /subscriptions/me/cancel ──────────────────────────────────────────


class TestCancelMySubscription:
    def test_cancel_active_subscription(
        self, client: TestClient, db: Session
    ) -> None:
        user, headers = _user_and_headers(client, db)
        plan = _create_plan(db, f"plan_{random_lower_string()}")
        sub = _create_subscription(db, user.id, plan.id)

        r = client.delete(
            f"{settings.API_V1_STR}/subscriptions/me/cancel",
            headers=headers,
        )
        assert r.status_code == 200
        assert "cancelled" in r.json()["message"].lower()

        # DB에서 상태 확인
        db.refresh(sub)
        assert sub.status == SubscriptionStatusEnum.cancelled
        assert sub.cancelled_at is not None

    def test_cancel_when_no_subscription_returns_404(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        r = client.delete(
            f"{settings.API_V1_STR}/subscriptions/me/cancel",
            headers=headers,
        )
        assert r.status_code == 404

    def test_requires_auth(self, client: TestClient) -> None:
        r = client.delete(f"{settings.API_V1_STR}/subscriptions/me/cancel")
        assert r.status_code == 401

    def test_cancelled_subscription_not_returned_in_me(
        self, client: TestClient, db: Session
    ) -> None:
        """취소 후 /me 조회 시 None 반환."""
        user, headers = _user_and_headers(client, db)
        plan = _create_plan(db, f"plan_{random_lower_string()}")
        _create_subscription(db, user.id, plan.id)

        client.delete(
            f"{settings.API_V1_STR}/subscriptions/me/cancel",
            headers=headers,
        )

        r = client.get(
            f"{settings.API_V1_STR}/subscriptions/me", headers=headers
        )
        assert r.json() is None


class TestGetPaymentHistory:
    def test_returns_empty_history_for_new_user(
        self, client: TestClient, db: Session
    ) -> None:
        _, headers = _user_and_headers(client, db)
        r = client.get(
            f"{settings.API_V1_STR}/subscriptions/history", headers=headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 0
        assert r.json()["data"] == []

    def test_returns_user_payment_history(
        self, client: TestClient, db: Session
    ) -> None:
        user, headers = _user_and_headers(client, db)
        plan = _create_plan(db, f"plan_{random_lower_string()}")
        subscription = _create_subscription(db, user.id, plan.id)
        history = PaymentHistory(
            user_id=user.id,
            subscription_id=subscription.id,
            plan_id=plan.id,
            amount_krw=9900,
            status="paid",
            pg_provider="test-pg",
            pg_payment_id=f"pay-{uuid.uuid4()}",
            paid_at=datetime.now(UTC),
        )
        db.add(history)
        db.commit()
        db.refresh(history)

        r = client.get(
            f"{settings.API_V1_STR}/subscriptions/history",
            headers=headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["data"][0]["id"] == str(history.id)
        assert data["data"][0]["amount_krw"] == 9900

    def test_requires_auth(self, client: TestClient) -> None:
        r = client.get(f"{settings.API_V1_STR}/subscriptions/history")
        assert r.status_code == 401
