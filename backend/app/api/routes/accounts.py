import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep
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
