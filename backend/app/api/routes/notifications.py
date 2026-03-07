import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Message,
    NotificationPublic,
    NotificationsPublic,
    NotificationSettingsPublic,
    NotificationSettingsUpdate,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=NotificationsPublic)
def read_notifications(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
    unread_only: bool = False,
) -> Any:
    """사용자 알림 목록 조회 (최신순)."""
    notifications = crud.get_notifications_by_user(
        session=session,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        unread_only=unread_only,
    )
    count = crud.count_notifications_by_user(
        session=session, user_id=current_user.id, unread_only=unread_only
    )
    return NotificationsPublic(data=notifications, count=count)


@router.post("/{id}/read", response_model=NotificationPublic)
def mark_notification_as_read(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """알림 읽음 처리."""
    notification = crud.get_notification(session=session, notification_id=id)
    if not notification or notification.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    return crud.mark_notification_read(session=session, notification=notification)


@router.post("/read-all", response_model=Message)
def mark_all_notifications_read(
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """모든 알림 읽음 처리."""
    notifications = crud.get_notifications_by_user(
        session=session,
        user_id=current_user.id,
        limit=1000,
        unread_only=True,
    )
    for notification in notifications:
        crud.mark_notification_read(session=session, notification=notification)
    return Message(message=f"{len(notifications)} notifications marked as read")


@router.get("/settings", response_model=NotificationSettingsPublic)
def read_notification_settings(
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    return crud.get_or_create_notification_settings(
        session=session, user_id=current_user.id
    )


@router.patch("/settings", response_model=NotificationSettingsPublic)
def update_notification_settings(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    settings_in: NotificationSettingsUpdate,
) -> Any:
    return crud.update_notification_settings(
        session=session,
        user_id=current_user.id,
        settings_in=settings_in,
    )
