import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum as PyEnum

from typing import Optional

from pydantic import EmailStr
from sqlalchemy import Column, DateTime, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ────────────────────────────────────────────────────────────────────


class ExchangeTypeEnum(str, PyEnum):
    binance = "binance"
    upbit = "upbit"
    kis = "kis"
    kiwoom = "kiwoom"


class BotTypeEnum(str, PyEnum):
    spot_grid = "spot_grid"
    position_snowball = "position_snowball"
    rebalancing = "rebalancing"
    spot_dca = "spot_dca"
    algo_orders = "algo_orders"


class BotStatusEnum(str, PyEnum):
    stopped = "stopped"
    pending = "pending"
    running = "running"
    error = "error"
    completed = "completed"


class SubscriptionStatusEnum(str, PyEnum):
    active = "active"
    cancelled = "cancelled"
    expired = "expired"
    past_due = "past_due"


# ── User ─────────────────────────────────────────────────────────────────────


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    exchange_accounts: list["ExchangeAccount"] = Relationship(
        back_populates="owner", cascade_delete=True
    )
    bots: list["Bot"] = Relationship(
        back_populates="owner", cascade_delete=True
    )
    subscription: Optional["UserSubscription"] = Relationship(back_populates="owner")


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


# ── ExchangeAccount ──────────────────────────────────────────────────────────


class ExchangeAccountBase(SQLModel):
    exchange: ExchangeTypeEnum
    label: str = Field(max_length=100)
    is_active: bool = True


class ExchangeAccount(ExchangeAccountBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    # 암호화된 API 자격증명 (복호화는 bot_engine에서만 수행)
    api_key_enc: str = Field(sa_type=Text())
    api_secret_enc: str = Field(sa_type=Text())
    extra_params_enc: str | None = Field(default=None, sa_type=Text())
    is_valid: bool = False
    last_verified_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))

    owner: User = Relationship(back_populates="exchange_accounts")
    bots: list["Bot"] = Relationship(back_populates="account")


class ExchangeAccountCreate(SQLModel):
    exchange: ExchangeTypeEnum
    label: str = Field(max_length=100)
    api_key: str = Field(min_length=1)      # 평문 — CRUD에서 암호화
    api_secret: str = Field(min_length=1)   # 평문 — CRUD에서 암호화
    extra_params: dict | None = None


class ExchangeAccountUpdate(SQLModel):
    label: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class ExchangeAccountPublic(ExchangeAccountBase):
    id: uuid.UUID
    is_valid: bool
    last_verified_at: datetime | None
    created_at: datetime


class ExchangeAccountsPublic(SQLModel):
    data: list[ExchangeAccountPublic]
    count: int


# ── Bot ──────────────────────────────────────────────────────────────────────


class BotBase(SQLModel):
    name: str = Field(max_length=100)
    bot_type: BotTypeEnum
    symbol: str | None = Field(default=None, max_length=30)
    base_currency: str | None = Field(default=None, max_length=20)
    quote_currency: str | None = Field(default=None, max_length=20)
    investment_amount: Decimal = Field(
        default=Decimal("0"),
        sa_type=Numeric(precision=36, scale=18),
    )
    stop_loss_pct: Decimal | None = Field(
        default=None,
        sa_type=Numeric(precision=10, scale=4),
    )
    take_profit_pct: Decimal | None = Field(
        default=None,
        sa_type=Numeric(precision=10, scale=4),
    )


class Bot(BotBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    account_id: uuid.UUID = Field(foreign_key="exchangeaccount.id", ondelete="RESTRICT")
    status: BotStatusEnum = Field(default=BotStatusEnum.stopped)
    total_pnl: Decimal = Field(
        default=Decimal("0"),
        sa_type=Numeric(precision=36, scale=18),
    )
    total_pnl_pct: Decimal = Field(
        default=Decimal("0"),
        sa_type=Numeric(precision=10, scale=4),
    )
    total_fee: Decimal = Field(
        default=Decimal("0"),
        sa_type=Numeric(precision=36, scale=18),
    )
    error_message: str | None = Field(default=None, sa_type=Text())
    celery_task_id: str | None = Field(default=None, max_length=255)
    started_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    stopped_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))

    owner: User = Relationship(back_populates="bots")
    account: ExchangeAccount = Relationship(back_populates="bots")


class BotCreate(BotBase):
    account_id: uuid.UUID


class BotUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=100)
    stop_loss_pct: Decimal | None = None
    take_profit_pct: Decimal | None = None


class BotPublic(BotBase):
    id: uuid.UUID
    account_id: uuid.UUID
    status: BotStatusEnum
    total_pnl: Decimal
    total_pnl_pct: Decimal
    created_at: datetime


class BotsPublic(SQLModel):
    data: list[BotPublic]
    count: int


# ── SubscriptionPlan ─────────────────────────────────────────────────────────


class SubscriptionPlan(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=50, unique=True)
    display_name: str = Field(max_length=100)
    price_krw: int
    max_bots: int       # -1 = 무제한
    max_accounts: int
    features: dict = Field(
        default={},
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    is_active: bool = True
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )

    subscriptions: list["UserSubscription"] = Relationship(back_populates="plan")


# ── UserSubscription ─────────────────────────────────────────────────────────


class UserSubscription(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id", unique=True, ondelete="CASCADE"
    )
    plan_id: uuid.UUID = Field(
        foreign_key="subscriptionplan.id", ondelete="RESTRICT"
    )
    status: SubscriptionStatusEnum
    pg_subscription_id: str | None = Field(default=None, max_length=255)
    started_at: datetime = Field(sa_type=DateTime(timezone=True))
    expires_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    cancelled_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )

    owner: User = Relationship(back_populates="subscription")
    plan: SubscriptionPlan = Relationship(back_populates="subscriptions")
