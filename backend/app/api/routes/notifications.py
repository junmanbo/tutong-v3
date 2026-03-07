from typing import Any

from fastapi import APIRouter

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import NotificationSettingsPublic, NotificationSettingsUpdate

router = APIRouter(prefix="/notifications", tags=["notifications"])


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
