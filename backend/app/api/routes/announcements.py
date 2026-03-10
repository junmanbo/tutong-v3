import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Announcement,
    AnnouncementCreate,
    AnnouncementsPublic,
    AnnouncementPublic,
    AnnouncementUpdate,
    Message,
)

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.get("/", response_model=AnnouncementsPublic)
def read_announcements(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """공지사항 목록 조회. 일반 사용자는 게시된 공지만 조회."""
    items = crud.get_announcements(
        session=session,
        include_unpublished=bool(current_user.is_superuser),
        skip=skip,
        limit=limit,
    )
    return AnnouncementsPublic(data=items, count=len(items))


@router.get("/{id}", response_model=AnnouncementPublic)
def read_announcement(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    item = crud.get_announcement(session=session, announcement_id=id)
    if not item:
        raise HTTPException(status_code=404, detail="Announcement not found")
    if not current_user.is_superuser and not item.is_published:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return item


@router.post("/", response_model=AnnouncementPublic, status_code=201)
def create_announcement(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    announcement_in: AnnouncementCreate,
) -> Any:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    published_at = announcement_in.published_at
    if announcement_in.is_published and published_at is None:
        published_at = datetime.now(timezone.utc)

    announcement = Announcement(
        title=announcement_in.title,
        content=announcement_in.content,
        is_pinned=announcement_in.is_pinned,
        is_published=announcement_in.is_published,
        published_at=published_at,
        created_by=current_user.id,
    )
    return crud.create_announcement(session=session, announcement=announcement)


@router.patch("/{id}", response_model=AnnouncementPublic)
def update_announcement(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    announcement_in: AnnouncementUpdate,
) -> Any:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    announcement = crud.get_announcement(session=session, announcement_id=id)
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    update_data = announcement_in.model_dump(exclude_unset=True)
    if update_data.get("is_published") and update_data.get("published_at") is None:
        update_data["published_at"] = datetime.now(timezone.utc)

    return crud.update_announcement(
        session=session,
        announcement=announcement,
        data=update_data,
    )


@router.delete("/{id}", response_model=Message)
def delete_announcement(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    announcement = crud.get_announcement(session=session, announcement_id=id)
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    crud.delete_announcement(session=session, announcement=announcement)
    return Message(message="Announcement deleted")
