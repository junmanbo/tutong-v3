import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum as PyEnum

from typing import Optional

from pydantic import EmailStr
from sqlalchemy import Column, DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import INET, JSONB
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


class NotificationChannelEnum(str, PyEnum):
    email = "email"
    telegram = "telegram"
    web_push = "web_push"


class NotificationDeliveryStatusEnum(str, PyEnum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


# ── User ─────────────────────────────────────────────────────────────────────


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str = Field(default="", max_length=100)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str = Field(default="", max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    full_name: str = Field(
        default="",
        sa_column=Column("display_name", String(100), nullable=False, server_default=""),
    )
    hashed_password: str = Field(sa_column=Column("password_hash", String(255), nullable=True))
    is_email_verified: bool = False
    totp_secret: str | None = Field(default=None, max_length=64)
    totp_enabled: bool = False
    failed_login_count: int = 0
    locked_until: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    oauth_provider: str | None = Field(default=None, max_length=20)
    oauth_id: str | None = Field(default=None, max_length=255)
    role: str = Field(default="user", max_length=20)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    exchange_accounts: list["ExchangeAccount"] = Relationship(
        back_populates="owner", cascade_delete=True
    )
    bots: list["Bot"] = Relationship(
        back_populates="owner", cascade_delete=True
    )
    subscription: Optional["UserSubscription"] = Relationship(back_populates="owner")
    notification_settings: Optional["NotificationSettings"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    notifications: list["Notification"] = Relationship(
        back_populates="user", cascade_delete=True
    )


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


class ExchangeAccountConnectionTest(SQLModel):
    exchange: ExchangeTypeEnum
    api_key: str = Field(min_length=1)
    api_secret: str = Field(min_length=1)
    extra_params: dict | None = None


class ExchangeAccountConnectionTestResult(SQLModel):
    is_valid: bool
    message: str


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
    config: dict = Field(
        default={},
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
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
    logs: list["BotLog"] = Relationship(back_populates="bot")
    notifications: list["Notification"] = Relationship(back_populates="bot")


class BotCreate(BotBase):
    account_id: uuid.UUID
    config: dict = Field(default={})


class BotUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=100)
    stop_loss_pct: Decimal | None = None
    take_profit_pct: Decimal | None = None


class BotPublic(BotBase):
    id: uuid.UUID
    account_id: uuid.UUID
    status: BotStatusEnum
    config: dict
    total_pnl: Decimal
    total_pnl_pct: Decimal
    created_at: datetime


class BotsPublic(SQLModel):
    data: list[BotPublic]
    count: int


class BotLogBase(SQLModel):
    event_type: str = Field(max_length=50)
    level: str = Field(default="info", max_length=20)
    message: str = Field(sa_type=Text())
    payload: dict = Field(
        default={},
        sa_column=Column("metadata", JSONB, nullable=False, server_default="{}"),
    )


class BotLog(BotLogBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    bot_id: uuid.UUID = Field(foreign_key="bot.id", ondelete="CASCADE")
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )

    bot: Bot = Relationship(back_populates="logs")


class BotLogPublic(BotLogBase):
    id: uuid.UUID
    bot_id: uuid.UUID
    created_at: datetime


class BotLogsPublic(SQLModel):
    data: list[BotLogPublic]
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


# ── Notifications ────────────────────────────────────────────────────────────


class NotificationSettingsBase(SQLModel):
    email_enabled: bool = True
    telegram_enabled: bool = False
    telegram_chat_id: str | None = Field(default=None, max_length=100)
    notify_bot_start: bool = True
    notify_bot_stop: bool = True
    notify_bot_error: bool = True
    notify_take_profit: bool = True
    notify_stop_loss: bool = True
    notify_account_error: bool = True


class NotificationSettings(NotificationSettingsBase, table=True):
    user_id: uuid.UUID = Field(
        primary_key=True, foreign_key="user.id", ondelete="CASCADE"
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )

    user: User = Relationship(back_populates="notification_settings")


class NotificationSettingsUpdate(SQLModel):
    email_enabled: bool | None = None
    telegram_enabled: bool | None = None
    telegram_chat_id: str | None = Field(default=None, max_length=100)
    notify_bot_start: bool | None = None
    notify_bot_stop: bool | None = None
    notify_bot_error: bool | None = None
    notify_take_profit: bool | None = None
    notify_stop_loss: bool | None = None
    notify_account_error: bool | None = None


class NotificationSettingsPublic(NotificationSettingsBase):
    user_id: uuid.UUID
    updated_at: datetime


class NotificationBase(SQLModel):
    channel: NotificationChannelEnum = NotificationChannelEnum.email
    event_type: str = Field(max_length=50)
    title: str = Field(max_length=255)
    body: str = Field(sa_type=Text())
    is_read: bool = False
    payload: dict = Field(
        default={},
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )


class Notification(NotificationBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    bot_id: uuid.UUID | None = Field(default=None, foreign_key="bot.id", ondelete="SET NULL")
    delivery_status: NotificationDeliveryStatusEnum = Field(
        default=NotificationDeliveryStatusEnum.pending
    )
    attempt_count: int = 0
    last_error: str | None = Field(default=None, sa_type=Text())
    sent_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    failed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )

    user: User = Relationship(back_populates="notifications")
    bot: Bot | None = Relationship(back_populates="notifications")


class NotificationPublic(NotificationBase):
    id: uuid.UUID
    user_id: uuid.UUID
    bot_id: uuid.UUID | None
    delivery_status: NotificationDeliveryStatusEnum
    attempt_count: int
    last_error: str | None
    sent_at: datetime | None
    failed_at: datetime | None
    created_at: datetime


class NotificationsPublic(SQLModel):
    data: list[NotificationPublic]
    count: int


# ── Additional Tables from DB Design ─────────────────────────────────────────


class UserSession(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    refresh_token_hash: str = Field(unique=True, max_length=255)
    ip_address: str | None = Field(default=None, sa_type=INET())
    user_agent: str | None = Field(default=None, sa_type=Text())
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    revoked_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class PaymentHistory(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    subscription_id: uuid.UUID | None = Field(
        default=None, foreign_key="usersubscription.id", ondelete="SET NULL"
    )
    plan_id: uuid.UUID = Field(foreign_key="subscriptionplan.id", ondelete="RESTRICT")
    amount_krw: int
    status: str = Field(max_length=20)
    pg_provider: str | None = Field(default=None, max_length=50)
    pg_payment_id: str | None = Field(default=None, unique=True, max_length=255)
    paid_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class BotConfigGrid(SQLModel, table=True):
    bot_id: uuid.UUID = Field(primary_key=True, foreign_key="bot.id", ondelete="CASCADE")
    upper_price: Decimal = Field(sa_type=Numeric(precision=36, scale=18))
    lower_price: Decimal = Field(sa_type=Numeric(precision=36, scale=18))
    grid_count: int
    grid_type: str = Field(max_length=20)
    quantity_per_grid: Decimal = Field(sa_type=Numeric(precision=36, scale=18))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class BotConfigSnowball(SQLModel, table=True):
    bot_id: uuid.UUID = Field(primary_key=True, foreign_key="bot.id", ondelete="CASCADE")
    initial_amount: Decimal = Field(sa_type=Numeric(precision=36, scale=18))
    drop_trigger_pct: Decimal = Field(sa_type=Numeric(precision=10, scale=4))
    max_layers: int
    multiplier: Decimal = Field(default=Decimal("1"), sa_type=Numeric(precision=10, scale=4))
    take_profit_pct: Decimal = Field(sa_type=Numeric(precision=10, scale=4))
    current_layer: int = 0
    avg_entry_price: Decimal | None = Field(default=None, sa_type=Numeric(precision=36, scale=18))
    total_invested: Decimal = Field(default=Decimal("0"), sa_type=Numeric(precision=36, scale=18))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class BotConfigRebalancing(SQLModel, table=True):
    bot_id: uuid.UUID = Field(primary_key=True, foreign_key="bot.id", ondelete="CASCADE")
    rebal_mode: str = Field(max_length=30)
    interval_unit: str | None = Field(default=None, max_length=20)
    interval_value: int | None = None
    deviation_threshold_pct: Decimal | None = Field(
        default=None, sa_type=Numeric(precision=10, scale=4)
    )
    last_rebalanced_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class BotConfigRebalAsset(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("bot_id", "asset_symbol", name="uq_botconfigrebalasset_bot_asset"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    bot_id: uuid.UUID = Field(foreign_key="bot.id", ondelete="CASCADE")
    asset_symbol: str = Field(max_length=20)
    target_weight_pct: Decimal = Field(sa_type=Numeric(precision=10, scale=4))
    current_weight_pct: Decimal | None = Field(default=None, sa_type=Numeric(precision=10, scale=4))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class BotConfigDca(SQLModel, table=True):
    bot_id: uuid.UUID = Field(primary_key=True, foreign_key="bot.id", ondelete="CASCADE")
    order_amount: Decimal = Field(sa_type=Numeric(precision=36, scale=18))
    interval_unit: str = Field(max_length=20)
    interval_value: int = 1
    total_orders: int | None = None
    executed_orders: int = 0
    avg_entry_price: Decimal | None = Field(default=None, sa_type=Numeric(precision=36, scale=18))
    next_execute_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class BotConfigAlgo(SQLModel, table=True):
    bot_id: uuid.UUID = Field(primary_key=True, foreign_key="bot.id", ondelete="CASCADE")
    order_side: str = Field(max_length=10)
    total_quantity: Decimal | None = Field(default=None, sa_type=Numeric(36, 18))
    total_amount: Decimal | None = Field(default=None, sa_type=Numeric(36, 18))
    algo_type: str = Field(default="twap", max_length=20)
    execute_start_at: datetime = Field(sa_type=DateTime(timezone=True))
    execute_end_at: datetime = Field(sa_type=DateTime(timezone=True))
    split_count: int
    executed_count: int = 0
    avg_fill_price: Decimal | None = Field(default=None, sa_type=Numeric(36, 18))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class BotOrder(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    bot_id: uuid.UUID = Field(foreign_key="bot.id", ondelete="CASCADE")
    exchange_order_id: str = Field(max_length=100)
    symbol: str = Field(max_length=30)
    side: str = Field(max_length=10)
    order_type: str = Field(max_length=20)
    status: str = Field(max_length=30)
    quantity: Decimal = Field(sa_type=Numeric(precision=36, scale=18))
    price: Decimal | None = Field(default=None, sa_type=Numeric(precision=36, scale=18))
    avg_fill_price: Decimal | None = Field(default=None, sa_type=Numeric(precision=36, scale=18))
    filled_quantity: Decimal = Field(default=Decimal("0"), sa_type=Numeric(precision=36, scale=18))
    fee: Decimal = Field(default=Decimal("0"), sa_type=Numeric(precision=36, scale=18))
    fee_currency: str | None = Field(default=None, max_length=20)
    grid_level: int | None = None
    layer_index: int | None = None
    placed_at: datetime = Field(sa_type=DateTime(timezone=True))
    filled_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class BotTrade(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(foreign_key="botorder.id", ondelete="CASCADE")
    bot_id: uuid.UUID = Field(foreign_key="bot.id", ondelete="CASCADE")
    exchange_trade_id: str | None = Field(default=None, max_length=100)
    quantity: Decimal = Field(sa_type=Numeric(precision=36, scale=18))
    price: Decimal = Field(sa_type=Numeric(precision=36, scale=18))
    fee: Decimal = Field(default=Decimal("0"), sa_type=Numeric(precision=36, scale=18))
    fee_currency: str | None = Field(default=None, max_length=20)
    is_maker: bool | None = None
    traded_at: datetime = Field(sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class BotSnapshot(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    bot_id: uuid.UUID = Field(foreign_key="bot.id", ondelete="CASCADE")
    total_pnl: Decimal = Field(sa_type=Numeric(precision=36, scale=18))
    total_pnl_pct: Decimal = Field(sa_type=Numeric(precision=10, scale=4))
    portfolio_value: Decimal = Field(sa_type=Numeric(precision=36, scale=18))
    snapshot_at: datetime = Field(sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class Announcement(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(max_length=255)
    content: str = Field(sa_type=Text())
    is_pinned: bool = False
    is_published: bool = False
    published_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_by: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class PaymentHistoryPublic(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    subscription_id: uuid.UUID | None
    plan_id: uuid.UUID
    amount_krw: int
    status: str
    pg_provider: str | None
    pg_payment_id: str | None
    paid_at: datetime | None
    created_at: datetime


class PaymentHistoriesPublic(SQLModel):
    data: list[PaymentHistoryPublic]
    count: int


class BotOrderPublic(SQLModel):
    id: uuid.UUID
    bot_id: uuid.UUID
    exchange_order_id: str
    symbol: str
    side: str
    order_type: str
    status: str
    quantity: Decimal
    price: Decimal | None
    avg_fill_price: Decimal | None
    filled_quantity: Decimal
    fee: Decimal
    fee_currency: str | None
    grid_level: int | None
    layer_index: int | None
    placed_at: datetime
    filled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BotOrdersPublic(SQLModel):
    data: list[BotOrderPublic]
    count: int


class BotTradePublic(SQLModel):
    id: uuid.UUID
    order_id: uuid.UUID
    bot_id: uuid.UUID
    exchange_trade_id: str | None
    quantity: Decimal
    price: Decimal
    fee: Decimal
    fee_currency: str | None
    is_maker: bool | None
    traded_at: datetime
    created_at: datetime


class BotTradesPublic(SQLModel):
    data: list[BotTradePublic]
    count: int


class BotSnapshotPublic(SQLModel):
    id: uuid.UUID
    bot_id: uuid.UUID
    total_pnl: Decimal
    total_pnl_pct: Decimal
    portfolio_value: Decimal
    snapshot_at: datetime
    created_at: datetime


class BotSnapshotsPublic(SQLModel):
    data: list[BotSnapshotPublic]
    count: int


class AnnouncementCreate(SQLModel):
    title: str = Field(max_length=255)
    content: str
    is_pinned: bool = False
    is_published: bool = False
    published_at: datetime | None = None


class AnnouncementUpdate(SQLModel):
    title: str | None = Field(default=None, max_length=255)
    content: str | None = None
    is_pinned: bool | None = None
    is_published: bool | None = None
    published_at: datetime | None = None


class AnnouncementPublic(SQLModel):
    id: uuid.UUID
    title: str
    content: str
    is_pinned: bool
    is_published: bool
    published_at: datetime | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AnnouncementsPublic(SQLModel):
    data: list[AnnouncementPublic]
    count: int
