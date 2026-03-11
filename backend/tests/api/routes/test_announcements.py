"""공지사항 API 엔드포인트 테스트."""
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import Announcement, UserCreate
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string

UTC = timezone.utc


def _superuser_headers(client: TestClient) -> dict[str, str]:
    return user_authentication_headers(
        client=client,
        email=settings.FIRST_SUPERUSER,
        password=settings.FIRST_SUPERUSER_PASSWORD,
    )


def _normal_user_headers(client: TestClient, db: Session) -> dict[str, str]:
    email = random_email()
    password = random_lower_string()
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=email, password=password),
    )
    return user_authentication_headers(client=client, email=user.email, password=password)


def _create_announcement(
    db: Session,
    *,
    created_by: uuid.UUID,
    is_published: bool,
) -> Announcement:
    announcement = Announcement(
        title=f"title-{random_lower_string()[:8]}",
        content="content",
        is_pinned=False,
        is_published=is_published,
        published_at=datetime.now(UTC) if is_published else None,
        created_by=created_by,
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    return announcement


class TestReadAnnouncements:
    def test_normal_user_reads_only_published(
        self, client: TestClient, db: Session
    ) -> None:
        headers = _normal_user_headers(client, db)
        super_headers = _superuser_headers(client)
        admin_user = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
        assert admin_user is not None

        published = _create_announcement(db, created_by=admin_user.id, is_published=True)
        unpublished = _create_announcement(db, created_by=admin_user.id, is_published=False)

        r = client.get(f"{settings.API_V1_STR}/announcements/", headers=headers)
        assert r.status_code == 200
        data = r.json()["data"]
        ids = {item["id"] for item in data}
        assert str(published.id) in ids
        assert str(unpublished.id) not in ids

        # superuser는 비게시 공지도 확인 가능
        r_admin = client.get(
            f"{settings.API_V1_STR}/announcements/", headers=super_headers
        )
        assert r_admin.status_code == 200
        assert r_admin.json()["count"] >= len(data)

    def test_requires_auth(self, client: TestClient) -> None:
        r = client.get(f"{settings.API_V1_STR}/announcements/")
        assert r.status_code == 401


class TestAnnouncementCrud:
    def test_superuser_can_create_update_delete(
        self, client: TestClient, db: Session
    ) -> None:
        headers = _superuser_headers(client)

        create_r = client.post(
            f"{settings.API_V1_STR}/announcements/",
            headers=headers,
            json={
                "title": "공지 테스트",
                "content": "본문",
                "is_pinned": True,
                "is_published": True,
            },
        )
        assert create_r.status_code == 201
        announcement_id = create_r.json()["id"]

        patch_r = client.patch(
            f"{settings.API_V1_STR}/announcements/{announcement_id}",
            headers=headers,
            json={"title": "공지 수정", "is_pinned": False},
        )
        assert patch_r.status_code == 200
        assert patch_r.json()["title"] == "공지 수정"
        assert patch_r.json()["is_pinned"] is False

        delete_r = client.delete(
            f"{settings.API_V1_STR}/announcements/{announcement_id}",
            headers=headers,
        )
        assert delete_r.status_code == 200

    def test_normal_user_cannot_write(
        self, client: TestClient, db: Session
    ) -> None:
        headers = _normal_user_headers(client, db)
        r = client.post(
            f"{settings.API_V1_STR}/announcements/",
            headers=headers,
            json={"title": "x", "content": "y"},
        )
        assert r.status_code == 403
