import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.core.db import engine
from app.models import Notification, NotificationChannelEnum
from app.utils import send_email

logger = logging.getLogger(__name__)


EVENT_BOT_START = "bot_started"
EVENT_BOT_STOP = "bot_stopped"
EVENT_BOT_ERROR = "bot_error"
EVENT_TAKE_PROFIT = "take_profit"
EVENT_STOP_LOSS = "stop_loss"
EVENT_ACCOUNT_API_ERROR = "account_api_error"

MAX_RETRIES = 3
RETRY_DELAYS_SEC = (1, 2, 4)


def _is_event_enabled(event_type: str, settings_row) -> bool:
    event_map = {
        EVENT_BOT_START: settings_row.notify_bot_start,
        EVENT_BOT_STOP: settings_row.notify_bot_stop,
        EVENT_BOT_ERROR: settings_row.notify_bot_error,
        EVENT_TAKE_PROFIT: settings_row.notify_take_profit,
        EVENT_STOP_LOSS: settings_row.notify_stop_loss,
        EVENT_ACCOUNT_API_ERROR: settings_row.notify_account_error,
    }
    return event_map.get(event_type, False)


def queue_notification_event(
    *,
    session: Session,
    user_id: uuid.UUID,
    event_type: str,
    title: str,
    body: str,
    bot_id: uuid.UUID | None = None,
    payload: dict | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> Notification | None:
    settings_row = crud.get_or_create_notification_settings(session=session, user_id=user_id)
    if not settings_row.email_enabled or not _is_event_enabled(event_type, settings_row):
        return None

    notification = crud.create_notification(
        session=session,
        user_id=user_id,
        bot_id=bot_id,
        event_type=event_type,
        title=title,
        body=body,
        channel=NotificationChannelEnum.email,
        payload=payload,
    )
    if background_tasks:
        background_tasks.add_task(deliver_notification_task, str(notification.id))
    else:
        deliver_notification_task(str(notification.id))
    return notification


def deliver_notification_task(notification_id: str) -> None:
    try:
        notification_uuid = uuid.UUID(notification_id)
    except ValueError:
        logger.error("Invalid notification id: %s", notification_id)
        return

    for attempt in range(1, MAX_RETRIES + 1):
        with Session(engine) as session:
            notification = session.exec(
                select(Notification)
                .where(Notification.id == notification_uuid)
                .options(selectinload(Notification.user))
            ).first()
            if notification is None:
                logger.warning("Notification not found: %s", notification_id)
                return

            if notification.channel != NotificationChannelEnum.email:
                crud.mark_notification_failed(
                    session=session,
                    notification=notification,
                    attempt_count=attempt,
                    last_error=f"Unsupported channel: {notification.channel.value}",
                    terminal=True,
                )
                return

            if not settings.emails_enabled:
                crud.mark_notification_failed(
                    session=session,
                    notification=notification,
                    attempt_count=attempt,
                    last_error="Email is not enabled in server settings",
                    terminal=True,
                )
                return

            to_email = notification.user.email if notification.user else None
            if not to_email:
                crud.mark_notification_failed(
                    session=session,
                    notification=notification,
                    attempt_count=attempt,
                    last_error="Notification target email not found",
                    terminal=True,
                )
                return

            try:
                html_content = _render_notification_html(
                    title=notification.title,
                    body=notification.body,
                    event_type=notification.event_type,
                    created_at=notification.created_at,
                )
                send_email(
                    email_to=str(to_email),
                    subject=notification.title,
                    html_content=html_content,
                )
                crud.mark_notification_sent(
                    session=session,
                    notification=notification,
                    attempt_count=attempt,
                )
                return
            except Exception as exc:
                is_terminal = attempt >= MAX_RETRIES
                crud.mark_notification_failed(
                    session=session,
                    notification=notification,
                    attempt_count=attempt,
                    last_error=str(exc),
                    terminal=is_terminal,
                )
                logger.warning(
                    "Notification delivery failed (id=%s, attempt=%s/%s): %s",
                    notification_id,
                    attempt,
                    MAX_RETRIES,
                    exc,
                )
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAYS_SEC[attempt - 1])


def _render_notification_html(
    *,
    title: str,
    body: str,
    event_type: str,
    created_at: datetime,
) -> str:
    created = created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        "<html><body>"
        f"<h2>{title}</h2>"
        f"<p>{body}</p>"
        f"<p><strong>Event:</strong> {event_type}</p>"
        f"<p><strong>Created:</strong> {created}</p>"
        "</body></html>"
    )
