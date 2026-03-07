import os
import uuid
from typing import Any

import redis as redis_lib
from celery import Celery
from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    BotCreate,
    BotLogsPublic,
    BotPublic,
    BotsPublic,
    BotStatusEnum,
    BotTypeEnum,
    BotUpdate,
    Message,
)

# Celery task 이름 매핑 (bot_type → task name)
_BOT_TASK_MAP: dict[BotTypeEnum, str] = {
    BotTypeEnum.spot_grid: "bot_engine.workers.spot_grid.run",
    BotTypeEnum.position_snowball: "bot_engine.workers.snowball.run",
    BotTypeEnum.rebalancing: "bot_engine.workers.rebalancing.run",
    BotTypeEnum.spot_dca: "bot_engine.workers.spot_dca.run",
    BotTypeEnum.algo_orders: "bot_engine.workers.algo_orders.run",
}

router = APIRouter(prefix="/bots", tags=["bots"])


@router.get("/", response_model=BotsPublic)
def read_bots(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """현재 사용자의 봇 목록 조회."""
    bots = crud.get_bots_by_user(
        session=session, user_id=current_user.id, skip=skip, limit=limit
    )
    return BotsPublic(data=bots, count=len(bots))


@router.get("/{id}", response_model=BotPublic)
def read_bot(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """봇 단건 조회."""
    bot = crud.get_bot(session=session, bot_id=id, user_id=current_user.id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return bot


@router.get("/{id}/logs", response_model=BotLogsPublic)
def read_bot_logs(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """봇 실행 로그 조회."""
    bot = crud.get_bot(session=session, bot_id=id, user_id=current_user.id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    logs = crud.get_bot_logs_by_user(
        session=session,
        bot_id=id,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return BotLogsPublic(data=logs, count=len(logs))


@router.post("/", response_model=BotPublic, status_code=201)
def create_bot(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    bot_in: BotCreate,
) -> Any:
    """봇 생성. 플랜 봇 한도 초과 시 403."""
    # 플랜 한도 체크
    max_bots = crud.get_user_bot_limit(session=session, user_id=current_user.id)
    if max_bots != -1:
        current_count = crud.count_active_bots(
            session=session, user_id=current_user.id
        )
        if current_count >= max_bots:
            raise HTTPException(
                status_code=403,
                detail=f"Bot limit reached for your plan ({max_bots} bots)",
            )

    # 계좌 소유권 확인
    account = crud.get_exchange_account(
        session=session,
        account_id=bot_in.account_id,
        user_id=current_user.id,
    )
    if not account:
        raise HTTPException(status_code=404, detail="Exchange account not found")

    return crud.create_bot(session=session, bot_in=bot_in, owner_id=current_user.id)


@router.patch("/{id}", response_model=BotPublic)
def update_bot(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    bot_in: BotUpdate,
) -> Any:
    """봇 설정 수정 (중지 상태에서만 가능)."""
    bot = crud.get_bot(session=session, bot_id=id, user_id=current_user.id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    if bot.status != BotStatusEnum.stopped:
        raise HTTPException(
            status_code=409, detail="Bot must be stopped before updating"
        )
    return crud.update_bot(session=session, bot=bot, bot_in=bot_in)


@router.delete("/{id}", response_model=Message)
def delete_bot(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """봇 삭제 - soft delete (중지 상태에서만 가능)."""
    bot = crud.get_bot(session=session, bot_id=id, user_id=current_user.id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    if bot.status != BotStatusEnum.stopped:
        raise HTTPException(
            status_code=409, detail="Bot must be stopped before deleting"
        )
    crud.delete_bot(session=session, bot=bot)
    return Message(message="Bot deleted successfully")


@router.post("/{id}/start", response_model=BotPublic)
def start_bot(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """봇 시작 (stopped/error → pending) 후 Celery 태스크 디스패치."""
    bot = crud.get_bot(session=session, bot_id=id, user_id=current_user.id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    if bot.status not in (BotStatusEnum.stopped, BotStatusEnum.error):
        raise HTTPException(
            status_code=409,
            detail=f"Bot cannot be started from status '{bot.status}'",
        )

    bot = crud.start_bot(session=session, bot=bot)  # → pending
    crud.create_bot_log(
        session=session,
        bot_id=bot.id,
        event_type="bot_start_requested",
        level="info",
        message="Bot start requested by user",
        payload={"status": bot.status.value},
    )

    task_name = _BOT_TASK_MAP.get(bot.bot_type)
    if task_name:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        celery_app = Celery(broker=redis_url, backend=redis_url)
        celery_app.send_task(task_name, kwargs={"bot_id": str(bot.id)})

    return bot


@router.post("/{id}/stop", response_model=BotPublic)
def stop_bot(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """봇 중지 요청 — Redis 중지 신호 설정 후 DB 상태 즉시 stopped 업데이트."""
    bot = crud.get_bot(session=session, bot_id=id, user_id=current_user.id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    if bot.status not in (BotStatusEnum.running, BotStatusEnum.pending):
        raise HTTPException(
            status_code=409,
            detail=f"Bot cannot be stopped from status '{bot.status}'",
        )

    # Redis 중지 신호 → Worker가 다음 루프에서 감지하고 정상 종료
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = redis_lib.from_url(redis_url, decode_responses=True)
    r.set(f"bot:{str(bot.id)}:stop", "1")
    stopped_bot = crud.stop_bot(session=session, bot=bot)  # DB 즉시 stopped
    crud.create_bot_log(
        session=session,
        bot_id=stopped_bot.id,
        event_type="bot_stop_requested",
        level="info",
        message="Bot stop requested by user",
        payload={"status": stopped_bot.status.value},
    )
    return stopped_bot
