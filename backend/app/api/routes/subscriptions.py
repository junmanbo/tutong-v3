"""구독/결제 관련 API.

현재 PG 연동 없이 플랜 조회 및 구독 현황만 제공합니다.
"""
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import SQLModel, select

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Message,
    PaymentHistoriesPublic,
    SubscriptionPlan,
    SubscriptionStatusEnum,
    UserSubscription,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


# ── 응답 스키마 ───────────────────────────────────────────────────────────────


class SubscriptionPlanPublic(SQLModel):
    id: uuid.UUID
    name: str
    display_name: str
    price_krw: int
    max_bots: int
    max_accounts: int
    features: dict
    is_active: bool
    created_at: datetime


class SubscriptionPublic(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    plan_id: uuid.UUID
    status: SubscriptionStatusEnum
    pg_subscription_id: str | None
    started_at: datetime
    expires_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime


@router.get("/plans", response_model=list[SubscriptionPlanPublic])
def list_plans(session: SessionDep) -> Any:
    """활성 구독 플랜 목록 조회."""
    plans = session.exec(
        select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)  # noqa: E712
    ).all()
    return list(plans)


@router.get("/plans/{plan_id}", response_model=SubscriptionPlanPublic)
def get_plan(session: SessionDep, plan_id: str) -> Any:
    """구독 플랜 상세 조회 (id 또는 name)."""
    plan = session.exec(
        select(SubscriptionPlan).where(SubscriptionPlan.name == plan_id)
    ).first()
    if not plan:
        try:
            import uuid
            plan = session.get(SubscriptionPlan, uuid.UUID(plan_id))
        except ValueError:
            plan = None
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


# ── 현재 구독 조회 ────────────────────────────────────────────────────────────


@router.get("/me", response_model=SubscriptionPublic | None)
def get_my_subscription(
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """현재 사용자의 구독 정보 조회."""
    subscription = session.exec(
        select(UserSubscription).where(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == SubscriptionStatusEnum.active,
        )
    ).first()
    return subscription


@router.delete("/me/cancel", response_model=Message)
def cancel_my_subscription(
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """구독 취소 요청. (실제 PG 연동 전 상태 변경만 수행)"""
    from datetime import datetime, timezone

    subscription = session.exec(
        select(UserSubscription).where(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == SubscriptionStatusEnum.active,
        )
    ).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")
    subscription.status = SubscriptionStatusEnum.cancelled
    subscription.cancelled_at = datetime.now(timezone.utc)
    subscription.updated_at = datetime.now(timezone.utc)
    session.add(subscription)
    session.commit()
    return Message(message="Subscription cancelled successfully")


@router.get("/history", response_model=PaymentHistoriesPublic)
def get_my_payment_history(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """현재 사용자의 결제 내역 조회."""
    history = crud.get_payment_history_by_user(
        session=session,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return PaymentHistoriesPublic(data=history, count=len(history))
