import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models import (
    Announcement,
    Bot,
    BotOrder,
    BotSnapshot,
    BotTrade,
    BotCreate,
    BotLog,
    BotUpdate,
    ExchangeAccount,
    ExchangeAccountCreate,
    ExchangeAccountUpdate,
    Notification,
    NotificationChannelEnum,
    NotificationDeliveryStatusEnum,
    NotificationSettings,
    NotificationSettingsUpdate,
    PaymentHistory,
    SubscriptionStatusEnum,
    User,
    UserCreate,
    UserUpdate,
    UserSubscription,
)


# ── User ─────────────────────────────────────────────────────────────────────


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create,
        update={
            "hashed_password": get_password_hash(user_create.password),
            "full_name": user_create.full_name or "",
        },
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    if "full_name" in user_data and user_data["full_name"] is None:
        user_data["full_name"] = ""
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    if not db_user.hashed_password:
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
    return db_user


# ── ExchangeAccount ──────────────────────────────────────────────────────────


def get_exchange_accounts_by_user(
    *, session: Session, user_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> list[ExchangeAccount]:
    statement = (
        select(ExchangeAccount)
        .where(
            ExchangeAccount.user_id == user_id,
            ExchangeAccount.deleted_at.is_(None),
        )
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_exchange_account(
    *, session: Session, account_id: uuid.UUID, user_id: uuid.UUID
) -> ExchangeAccount | None:
    statement = select(ExchangeAccount).where(
        ExchangeAccount.id == account_id,
        ExchangeAccount.user_id == user_id,
        ExchangeAccount.deleted_at.is_(None),
    )
    return session.exec(statement).first()


def count_active_accounts(*, session: Session, user_id: uuid.UUID) -> int:
    accounts = get_exchange_accounts_by_user(session=session, user_id=user_id)
    return len(accounts)


def create_exchange_account(
    *,
    session: Session,
    account_in: ExchangeAccountCreate,
    owner_id: uuid.UUID,
) -> ExchangeAccount:
    from app.core.config import settings
    from app.core.crypto import encrypt

    api_key_enc = encrypt(account_in.api_key, settings.ENCRYPTION_KEY)
    api_secret_enc = encrypt(account_in.api_secret, settings.ENCRYPTION_KEY)
    extra_params_enc: str | None = None
    if account_in.extra_params:
        extra_params_enc = encrypt(
            json.dumps(account_in.extra_params), settings.ENCRYPTION_KEY
        )

    account = ExchangeAccount(
        exchange=account_in.exchange,
        label=account_in.label,
        user_id=owner_id,
        api_key_enc=api_key_enc,
        api_secret_enc=api_secret_enc,
        extra_params_enc=extra_params_enc,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def update_exchange_account(
    *,
    session: Session,
    account: ExchangeAccount,
    account_in: ExchangeAccountUpdate,
) -> ExchangeAccount:
    update_data = account_in.model_dump(exclude_unset=True)
    account.sqlmodel_update(update_data)
    account.updated_at = datetime.now(timezone.utc)
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def delete_exchange_account(*, session: Session, account: ExchangeAccount) -> None:
    account.deleted_at = datetime.now(timezone.utc)
    session.add(account)
    session.commit()


# ── Bot ───────────────────────────────────────────────────────────────────────


def get_bots_by_user(
    *, session: Session, user_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> list[Bot]:
    statement = (
        select(Bot)
        .where(
            Bot.user_id == user_id,
            Bot.deleted_at.is_(None),
        )
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_bot(
    *, session: Session, bot_id: uuid.UUID, user_id: uuid.UUID
) -> Bot | None:
    statement = select(Bot).where(
        Bot.id == bot_id,
        Bot.user_id == user_id,
        Bot.deleted_at.is_(None),
    )
    return session.exec(statement).first()


def count_active_bots(*, session: Session, user_id: uuid.UUID) -> int:
    return len(get_bots_by_user(session=session, user_id=user_id))


def get_user_bot_limit(*, session: Session, user_id: uuid.UUID) -> int:
    """사용자 플랜의 봇 최대 한도 반환. -1 은 무제한, 구독 없으면 Free 기본값 1."""
    statement = select(UserSubscription).where(
        UserSubscription.user_id == user_id,
        UserSubscription.status == SubscriptionStatusEnum.active,
    )
    subscription = session.exec(statement).first()
    if subscription is None:
        return 1
    return subscription.plan.max_bots


def create_bot(
    *,
    session: Session,
    bot_in: BotCreate,
    owner_id: uuid.UUID,
) -> Bot:
    from app.models import BotStatusEnum

    bot = Bot.model_validate(
        bot_in,
        update={
            "user_id": owner_id,
            "status": BotStatusEnum.stopped,
        },
    )
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return bot


def update_bot(
    *,
    session: Session,
    bot: Bot,
    bot_in: BotUpdate,
) -> Bot:
    update_data = bot_in.model_dump(exclude_unset=True)
    bot.sqlmodel_update(update_data)
    bot.updated_at = datetime.now(timezone.utc)
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return bot


def delete_bot(*, session: Session, bot: Bot) -> None:
    bot.deleted_at = datetime.now(timezone.utc)
    session.add(bot)
    session.commit()


def start_bot(*, session: Session, bot: Bot) -> Bot:
    from app.models import BotStatusEnum

    bot.status = BotStatusEnum.pending
    bot.started_at = datetime.now(timezone.utc)
    bot.updated_at = datetime.now(timezone.utc)
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return bot


def stop_bot(*, session: Session, bot: Bot) -> Bot:
    from app.models import BotStatusEnum

    bot.status = BotStatusEnum.stopped
    bot.stopped_at = datetime.now(timezone.utc)
    bot.updated_at = datetime.now(timezone.utc)
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return bot


def create_bot_log(
    *,
    session: Session,
    bot_id: uuid.UUID,
    event_type: str,
    level: str,
    message: str,
    payload: dict | None = None,
) -> BotLog:
    log = BotLog(
        bot_id=bot_id,
        event_type=event_type,
        level=level,
        message=message,
        payload=payload or {},
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


def get_bot_logs_by_user(
    *,
    session: Session,
    bot_id: uuid.UUID,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[BotLog]:
    statement = (
        select(BotLog)
        .join(Bot, Bot.id == BotLog.bot_id)
        .where(
            BotLog.bot_id == bot_id,
            Bot.user_id == user_id,
            Bot.deleted_at.is_(None),
        )
        .order_by(BotLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_bot_orders_by_user(
    *,
    session: Session,
    bot_id: uuid.UUID,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[BotOrder]:
    statement = (
        select(BotOrder)
        .join(Bot, Bot.id == BotOrder.bot_id)
        .where(
            BotOrder.bot_id == bot_id,
            Bot.user_id == user_id,
            Bot.deleted_at.is_(None),
        )
        .order_by(BotOrder.placed_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_bot_trades_by_user(
    *,
    session: Session,
    bot_id: uuid.UUID,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[BotTrade]:
    statement = (
        select(BotTrade)
        .join(Bot, Bot.id == BotTrade.bot_id)
        .where(
            BotTrade.bot_id == bot_id,
            Bot.user_id == user_id,
            Bot.deleted_at.is_(None),
        )
        .order_by(BotTrade.traded_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_bot_snapshots_by_user(
    *,
    session: Session,
    bot_id: uuid.UUID,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[BotSnapshot]:
    statement = (
        select(BotSnapshot)
        .join(Bot, Bot.id == BotSnapshot.bot_id)
        .where(
            BotSnapshot.bot_id == bot_id,
            Bot.user_id == user_id,
            Bot.deleted_at.is_(None),
        )
        .order_by(BotSnapshot.snapshot_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


# ── Notification ──────────────────────────────────────────────────────────────


def get_notification_settings(*, session: Session, user_id: uuid.UUID) -> NotificationSettings | None:
    statement = select(NotificationSettings).where(NotificationSettings.user_id == user_id)
    return session.exec(statement).first()


def get_or_create_notification_settings(
    *, session: Session, user_id: uuid.UUID
) -> NotificationSettings:
    settings = get_notification_settings(session=session, user_id=user_id)
    if settings:
        return settings

    settings = NotificationSettings(user_id=user_id)
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


def update_notification_settings(
    *,
    session: Session,
    user_id: uuid.UUID,
    settings_in: NotificationSettingsUpdate,
) -> NotificationSettings:
    settings = get_or_create_notification_settings(session=session, user_id=user_id)
    update_data = settings_in.model_dump(exclude_unset=True)
    settings.sqlmodel_update(update_data)
    settings.updated_at = datetime.now(timezone.utc)
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


def create_notification(
    *,
    session: Session,
    user_id: uuid.UUID,
    event_type: str,
    title: str,
    body: str,
    bot_id: uuid.UUID | None = None,
    channel: NotificationChannelEnum = NotificationChannelEnum.email,
    payload: dict | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        bot_id=bot_id,
        channel=channel,
        event_type=event_type,
        title=title,
        body=body,
        payload=payload or {},
    )
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification


def get_notifications_by_user(
    *,
    session: Session,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
    unread_only: bool = False,
) -> list[Notification]:
    statement = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if unread_only:
        statement = statement.where(Notification.is_read == False)  # noqa: E712
    return list(session.exec(statement).all())


def count_notifications_by_user(
    *, session: Session, user_id: uuid.UUID, unread_only: bool = False
) -> int:
    notifications = get_notifications_by_user(
        session=session, user_id=user_id, limit=1000, unread_only=unread_only
    )
    return len(notifications)


def mark_notification_read(
    *, session: Session, notification: Notification
) -> Notification:
    notification.is_read = True
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification


def get_notification(*, session: Session, notification_id: uuid.UUID) -> Notification | None:
    return session.get(Notification, notification_id)


def mark_notification_sent(
    *,
    session: Session,
    notification: Notification,
    attempt_count: int,
) -> Notification:
    now = datetime.now(timezone.utc)
    notification.delivery_status = NotificationDeliveryStatusEnum.sent
    notification.attempt_count = attempt_count
    notification.sent_at = now
    notification.failed_at = None
    notification.last_error = None
    notification.updated_at = now
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification


def mark_notification_failed(
    *,
    session: Session,
    notification: Notification,
    attempt_count: int,
    last_error: str,
    terminal: bool,
) -> Notification:
    now = datetime.now(timezone.utc)
    notification.delivery_status = (
        NotificationDeliveryStatusEnum.failed
        if terminal
        else NotificationDeliveryStatusEnum.pending
    )
    notification.attempt_count = attempt_count
    notification.last_error = last_error
    notification.failed_at = now if terminal else None
    notification.updated_at = now
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification


# ── PaymentHistory ───────────────────────────────────────────────────────────


def get_payment_history_by_user(
    *,
    session: Session,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[PaymentHistory]:
    statement = (
        select(PaymentHistory)
        .where(PaymentHistory.user_id == user_id)
        .order_by(PaymentHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


# ── Announcements ────────────────────────────────────────────────────────────


def get_announcements(
    *,
    session: Session,
    include_unpublished: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> list[Announcement]:
    statement = select(Announcement)
    if not include_unpublished:
        statement = statement.where(Announcement.is_published == True)  # noqa: E712
    statement = (
        statement.order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_announcement(*, session: Session, announcement_id: uuid.UUID) -> Announcement | None:
    return session.get(Announcement, announcement_id)


def create_announcement(
    *,
    session: Session,
    announcement: Announcement,
) -> Announcement:
    session.add(announcement)
    session.commit()
    session.refresh(announcement)
    return announcement


def update_announcement(
    *,
    session: Session,
    announcement: Announcement,
    data: dict[str, Any],
) -> Announcement:
    announcement.sqlmodel_update(data)
    announcement.updated_at = datetime.now(timezone.utc)
    session.add(announcement)
    session.commit()
    session.refresh(announcement)
    return announcement


def delete_announcement(*, session: Session, announcement: Announcement) -> None:
    session.delete(announcement)
    session.commit()
