"""봇 API 부하 테스트.

실거래 호출 없이 봇 시작/중지 디스패치 경로가
100개 이상 봇 요청에서 정상 동작하는지 검증한다.
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import BotCreate, UserCreate
from tests.utils.account import create_random_account
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string

LOAD_BOT_COUNT = 100


def _create_user_and_headers(client: TestClient, db: Session) -> tuple:
    email = random_email()
    password = random_lower_string()
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=email, password=password),
    )
    headers = user_authentication_headers(
        client=client,
        email=email,
        password=password,
    )
    return user, headers


def _create_load_bots(
    *,
    db: Session,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    count: int,
) -> list[uuid.UUID]:
    bot_ids: list[uuid.UUID] = []
    for idx in range(count):
        bot = crud.create_bot(
            session=db,
            bot_in=BotCreate(
                name=f"load-bot-{idx}",
                bot_type="spot_dca",
                symbol="SOL/KRW",
                investment_amount="100000",
                account_id=account_id,
                config={
                    "amount_per_order": "10000",
                    "interval_seconds": 300,
                    "order_type": "market",
                    "total_orders": 10,
                },
            ),
            owner_id=user_id,
        )
        bot_ids.append(bot.id)
    return bot_ids


def test_start_100_bots_load_dispatch(
    client: TestClient,
    db: Session,
) -> None:
    """100개 봇 시작 요청이 모두 pending + Celery 디스패치 되어야 한다."""
    user, headers = _create_user_and_headers(client, db)
    account = create_random_account(db, user.id)
    bot_ids = _create_load_bots(
        db=db,
        user_id=user.id,
        account_id=account.id,
        count=LOAD_BOT_COUNT,
    )

    mock_celery = MagicMock()
    with (
        patch("app.api.routes.bots.Celery", return_value=mock_celery),
        patch("app.api.routes.bots.queue_notification_event") as mock_notify,
    ):
        started_at = time.perf_counter()
        for bot_id in bot_ids:
            response = client.post(
                f"{settings.API_V1_STR}/bots/{bot_id}/start",
                headers=headers,
            )
            assert response.status_code == 200
            assert response.json()["status"] == "pending"
        elapsed = time.perf_counter() - started_at

    assert mock_celery.send_task.call_count == LOAD_BOT_COUNT
    assert mock_notify.call_count == LOAD_BOT_COUNT
    assert elapsed < 30


def test_stop_100_bots_load_signal(
    client: TestClient,
    db: Session,
) -> None:
    """pending 상태 100개 봇 중지 요청이 모두 Redis stop 신호를 기록해야 한다."""
    user, headers = _create_user_and_headers(client, db)
    account = create_random_account(db, user.id)
    bot_ids = _create_load_bots(
        db=db,
        user_id=user.id,
        account_id=account.id,
        count=LOAD_BOT_COUNT,
    )

    mock_celery = MagicMock()
    with patch("app.api.routes.bots.Celery", return_value=mock_celery):
        for bot_id in bot_ids:
            response = client.post(
                f"{settings.API_V1_STR}/bots/{bot_id}/start",
                headers=headers,
            )
            assert response.status_code == 200
            assert response.json()["status"] == "pending"

    mock_redis = MagicMock()
    with (
        patch("redis.from_url", return_value=mock_redis),
        patch("app.api.routes.bots.queue_notification_event") as mock_notify,
    ):
        started_at = time.perf_counter()
        for bot_id in bot_ids:
            response = client.post(
                f"{settings.API_V1_STR}/bots/{bot_id}/stop",
                headers=headers,
            )
            assert response.status_code == 200
            assert response.json()["status"] == "stopped"
        elapsed = time.perf_counter() - started_at

    assert mock_redis.set.call_count == LOAD_BOT_COUNT
    assert mock_notify.call_count == LOAD_BOT_COUNT
    stop_keys = {call.args[0] for call in mock_redis.set.call_args_list}
    expected_keys = {f"bot:{bot_id}:stop" for bot_id in bot_ids}
    assert stop_keys == expected_keys
    assert elapsed < 30
