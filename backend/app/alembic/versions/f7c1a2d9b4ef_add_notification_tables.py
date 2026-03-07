"""add_notification_tables

Revision ID: f7c1a2d9b4ef
Revises: 3a8f2e4b7c11
Create Date: 2026-03-07 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "f7c1a2d9b4ef"
down_revision = "3a8f2e4b7c11"
branch_labels = None
depends_on = None


notify_channel_enum = postgresql.ENUM(
    "email",
    "telegram",
    "web_push",
    name="notificationchannelenum",
    create_type=False,
)
notify_delivery_status_enum = postgresql.ENUM(
    "pending",
    "sent",
    "failed",
    name="notificationdeliverystatusenum",
    create_type=False,
)


def upgrade():
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE notificationchannelenum AS ENUM ('email', 'telegram', 'web_push');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE notificationdeliverystatusenum AS ENUM ('pending', 'sent', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    op.create_table(
        "notificationsettings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False),
        sa.Column("telegram_enabled", sa.Boolean(), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=100), nullable=True),
        sa.Column("notify_bot_start", sa.Boolean(), nullable=False),
        sa.Column("notify_bot_stop", sa.Boolean(), nullable=False),
        sa.Column("notify_bot_error", sa.Boolean(), nullable=False),
        sa.Column("notify_take_profit", sa.Boolean(), nullable=False),
        sa.Column("notify_stop_loss", sa.Boolean(), nullable=False),
        sa.Column("notify_account_error", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "notification",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("bot_id", sa.Uuid(), nullable=True),
        sa.Column("channel", notify_channel_enum, nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("delivery_status", notify_delivery_status_enum, nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bot.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_user_unread",
        "notification",
        ["user_id", "is_read"],
        unique=False,
        postgresql_where=sa.text("is_read = false"),
    )


def downgrade():
    op.drop_index("ix_notification_user_unread", table_name="notification")
    op.drop_table("notification")
    op.drop_table("notificationsettings")
    op.execute("DROP TYPE IF EXISTS notificationdeliverystatusenum")
    op.execute("DROP TYPE IF EXISTS notificationchannelenum")
