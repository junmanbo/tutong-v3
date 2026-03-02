"""거래소 계좌·봇 테스트 헬퍼."""
import uuid
from decimal import Decimal

from sqlmodel import Session

from app import crud
from app.models import (
    Bot,
    BotCreate,
    BotTypeEnum,
    ExchangeAccount,
    ExchangeAccountCreate,
    ExchangeTypeEnum,
)
from tests.utils.utils import random_lower_string


def create_random_account(db: Session, user_id: uuid.UUID) -> ExchangeAccount:
    """랜덤 거래소 계좌를 DB에 직접 생성."""
    account_in = ExchangeAccountCreate(
        exchange=ExchangeTypeEnum.binance,
        label=random_lower_string()[:20],
        api_key=random_lower_string(),
        api_secret=random_lower_string(),
    )
    return crud.create_exchange_account(
        session=db, account_in=account_in, owner_id=user_id
    )


def create_random_bot(
    db: Session, user_id: uuid.UUID, account_id: uuid.UUID
) -> Bot:
    """랜덤 봇을 DB에 직접 생성 (플랜 한도 체크 없음)."""
    bot_in = BotCreate(
        name=random_lower_string()[:20],
        bot_type=BotTypeEnum.spot_dca,
        symbol="BTC/USDT",
        investment_amount=Decimal("100"),
        account_id=account_id,
    )
    return crud.create_bot(session=db, bot_in=bot_in, owner_id=user_id)
