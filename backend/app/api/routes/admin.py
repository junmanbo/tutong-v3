"""관리자 전용 API.

superuser 권한이 있는 사용자만 접근 가능합니다.
"""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select

from app.api.deps import SessionDep, get_current_active_superuser
from app.models import (
    Bot,
    BotsPublic,
    Message,
    User,
    UserPublic,
    UsersPublic,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_active_superuser)],
)


# ── 사용자 관리 ───────────────────────────────────────────────────────────────


@router.get("/users", response_model=UsersPublic)
def admin_list_users(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """전체 사용자 목록 조회."""
    count = session.exec(select(func.count()).select_from(User)).one()
    users = session.exec(select(User).offset(skip).limit(limit)).all()
    return UsersPublic(data=list(users), count=count)


@router.get("/users/{user_id}", response_model=UserPublic)
def admin_get_user(session: SessionDep, user_id: uuid.UUID) -> Any:
    """사용자 상세 조회."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}/deactivate", response_model=Message)
def admin_deactivate_user(session: SessionDep, user_id: uuid.UUID) -> Any:
    """사용자 계정 정지."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    session.add(user)
    session.commit()
    return Message(message=f"User {user.email} deactivated")


@router.patch("/users/{user_id}/activate", response_model=Message)
def admin_activate_user(session: SessionDep, user_id: uuid.UUID) -> Any:
    """사용자 계정 정지 해제."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    session.add(user)
    session.commit()
    return Message(message=f"User {user.email} activated")


# ── 봇 모니터링 ───────────────────────────────────────────────────────────────


@router.get("/bots", response_model=BotsPublic)
def admin_list_bots(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """전체 봇 운영 현황 조회."""
    statement = (
        select(Bot)
        .where(Bot.deleted_at.is_(None))
        .offset(skip)
        .limit(limit)
    )
    bots = list(session.exec(statement).all())
    count_stmt = select(func.count()).select_from(Bot).where(Bot.deleted_at.is_(None))
    count = session.exec(count_stmt).one()
    return BotsPublic(data=bots, count=count)
