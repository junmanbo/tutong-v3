import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.crypto import decrypt
from app.exchange_adapters.base import BalanceItem
from app.exchange_adapters.factory import get_adapter
from app.models import (
    ExchangeAccountCreate,
    ExchangeAccountPublic,
    ExchangeAccountsPublic,
    ExchangeAccountUpdate,
    Message,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/", response_model=ExchangeAccountsPublic)
def read_accounts(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """현재 사용자의 거래소 계좌 목록 조회."""
    accounts = crud.get_exchange_accounts_by_user(
        session=session, user_id=current_user.id, skip=skip, limit=limit
    )
    return ExchangeAccountsPublic(data=accounts, count=len(accounts))


@router.get("/{id}", response_model=ExchangeAccountPublic)
def read_account(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """거래소 계좌 단건 조회."""
    account = crud.get_exchange_account(
        session=session, account_id=id, user_id=current_user.id
    )
    if not account:
        raise HTTPException(status_code=404, detail="Exchange account not found")
    return account


@router.post("/", response_model=ExchangeAccountPublic, status_code=201)
def create_account(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    account_in: ExchangeAccountCreate,
) -> Any:
    """거래소 계좌 등록. API Key/Secret은 AES-256-GCM으로 암호화 후 저장."""
    return crud.create_exchange_account(
        session=session, account_in=account_in, owner_id=current_user.id
    )


@router.patch("/{id}", response_model=ExchangeAccountPublic)
def update_account(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    account_in: ExchangeAccountUpdate,
) -> Any:
    """거래소 계좌 정보 수정 (label, is_active)."""
    account = crud.get_exchange_account(
        session=session, account_id=id, user_id=current_user.id
    )
    if not account:
        raise HTTPException(status_code=404, detail="Exchange account not found")
    return crud.update_exchange_account(
        session=session, account=account, account_in=account_in
    )


@router.delete("/{id}", response_model=Message)
def delete_account(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """거래소 계좌 삭제 (soft delete)."""
    account = crud.get_exchange_account(
        session=session, account_id=id, user_id=current_user.id
    )
    if not account:
        raise HTTPException(status_code=404, detail="Exchange account not found")
    crud.delete_exchange_account(session=session, account=account)
    return Message(message="Exchange account deleted successfully")


@router.get("/{id}/balance", response_model=list[BalanceItem])
def get_account_balance(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """거래소 계좌 잔고 조회.

    해당 계좌의 API Key로 거래소에 직접 조회합니다.
    잔고가 0인 자산은 제외하고 반환합니다.
    """
    account = crud.get_exchange_account(
        session=session, account_id=id, user_id=current_user.id
    )
    if not account:
        raise HTTPException(status_code=404, detail="Exchange account not found")

    try:
        api_key = decrypt(account.api_key_enc, settings.ENCRYPTION_KEY)
        api_secret = decrypt(account.api_secret_enc, settings.ENCRYPTION_KEY)
        extra_params: dict | None = None
        if account.extra_params_enc:
            extra_params = json.loads(
                decrypt(account.extra_params_enc, settings.ENCRYPTION_KEY)
            )
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to decrypt account credentials")

    adapter = get_adapter(
        exchange=account.exchange,
        api_key=api_key,
        api_secret=api_secret,
        extra_params=extra_params,
    )

    # FastAPI sync endpoint는 threadpool에서 실행 → new_event_loop 사용 가능
    loop = asyncio.new_event_loop()
    try:
        balances = loop.run_until_complete(adapter.get_balance())
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch balance from exchange: {exc}",
        )
    finally:
        loop.run_until_complete(adapter.close())
        loop.close()

    # 잔고가 있는 자산만 반환
    return [b for b in balances if b.free > 0 or b.locked > 0]
