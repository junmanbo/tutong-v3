"""align columns to db design spec

Revision ID: b7d4c2e9f1aa
Revises: a4f3b2c1d0e9
Create Date: 2026-03-10 00:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7d4c2e9f1aa"
down_revision: Union[str, None] = "a4f3b2c1d0e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # user
    op.alter_column("user", "hashed_password", new_column_name="password_hash")
    op.alter_column("user", "full_name", new_column_name="display_name")
    op.execute("UPDATE \"user\" SET display_name = '' WHERE display_name IS NULL")
    op.alter_column("user", "display_name", existing_type=sa.String(length=255), type_=sa.String(length=100), nullable=False)

    op.add_column("user", sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("user", sa.Column("totp_secret", sa.String(length=64), nullable=True))
    op.add_column("user", sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("user", sa.Column("failed_login_count", sa.SmallInteger(), nullable=False, server_default="0"))
    op.add_column("user", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user", sa.Column("oauth_provider", sa.String(length=20), nullable=True))
    op.add_column("user", sa.Column("oauth_id", sa.String(length=255), nullable=True))
    op.add_column("user", sa.Column("role", sa.String(length=20), nullable=False, server_default="user"))
    op.add_column("user", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
    op.add_column("user", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    op.execute('CREATE INDEX IF NOT EXISTS "idx_users_email" ON "user" (email) WHERE deleted_at IS NULL')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_users_oauth" ON "user" (oauth_provider, oauth_id) WHERE oauth_provider IS NOT NULL')

    # botlog payload -> metadata
    op.alter_column("botlog", "payload", new_column_name="metadata")
    op.execute('CREATE INDEX IF NOT EXISTS "idx_bl_bot_created" ON botlog (bot_id, created_at DESC)')
    op.execute("CREATE INDEX IF NOT EXISTS \"idx_bl_error\" ON botlog (bot_id, level) WHERE level = 'error'")

    # notification unread index
    op.execute("CREATE INDEX IF NOT EXISTS \"idx_noti_user_unread\" ON notification (user_id, is_read) WHERE is_read = false")

    # botconfigdca
    op.add_column("botconfigdca", sa.Column("executed_orders", sa.SmallInteger(), nullable=False, server_default="0"))
    op.add_column("botconfigdca", sa.Column("avg_entry_price", sa.Numeric(precision=36, scale=18), nullable=True))
    op.add_column("botconfigdca", sa.Column("next_execute_at", sa.DateTime(timezone=True), nullable=True))

    # botconfigalgo
    op.alter_column("botconfigalgo", "side", new_column_name="order_side")
    op.add_column("botconfigalgo", sa.Column("total_quantity", sa.Numeric(precision=36, scale=18), nullable=True))
    op.add_column("botconfigalgo", sa.Column("algo_type", sa.String(length=20), nullable=False, server_default="twap"))
    op.add_column("botconfigalgo", sa.Column("execute_start_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
    op.add_column("botconfigalgo", sa.Column("execute_end_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
    op.add_column("botconfigalgo", sa.Column("split_count", sa.SmallInteger(), nullable=False, server_default="1"))
    op.add_column("botconfigalgo", sa.Column("executed_count", sa.SmallInteger(), nullable=False, server_default="0"))
    op.add_column("botconfigalgo", sa.Column("avg_fill_price", sa.Numeric(precision=36, scale=18), nullable=True))
    op.execute("UPDATE botconfigalgo SET split_count = slices")
    op.drop_column("botconfigalgo", "slices")
    op.drop_column("botconfigalgo", "interval_seconds")
    op.drop_column("botconfigalgo", "order_type")

    # botorder
    op.alter_column("botorder", "exchange_order_id", existing_type=sa.String(length=255), type_=sa.String(length=100))
    op.add_column("botorder", sa.Column("grid_level", sa.SmallInteger(), nullable=True))
    op.add_column("botorder", sa.Column("layer_index", sa.SmallInteger(), nullable=True))
    op.add_column("botorder", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
    op.drop_column("botorder", "canceled_at")
    op.drop_column("botorder", "raw")
    op.execute('CREATE INDEX IF NOT EXISTS "idx_bo_bot_status" ON botorder (bot_id, status)')

    # bottrade
    op.alter_column("bottrade", "bot_order_id", new_column_name="order_id")
    op.alter_column("bottrade", "exchange_trade_id", existing_type=sa.String(length=255), type_=sa.String(length=100))
    op.add_column("bottrade", sa.Column("is_maker", sa.Boolean(), nullable=True))
    op.drop_column("bottrade", "symbol")
    op.drop_column("bottrade", "side")
    op.drop_column("bottrade", "amount")

    # botsnapshot
    op.add_column("botsnapshot", sa.Column("portfolio_value", sa.Numeric(precision=36, scale=18), nullable=False, server_default="0"))
    op.drop_column("botsnapshot", "total_equity")
    op.drop_column("botsnapshot", "cash_balance")
    op.drop_column("botsnapshot", "positions_value")

    # announcement
    op.alter_column("announcement", "body", new_column_name="content")
    op.alter_column("announcement", "is_active", new_column_name="is_published")
    op.alter_column("announcement", "starts_at", new_column_name="published_at")
    op.add_column("announcement", sa.Column("created_by", sa.Uuid(), nullable=True))
    op.execute("""
        UPDATE announcement
        SET created_by = (
            SELECT id FROM "user" ORDER BY created_at ASC LIMIT 1
        )
        WHERE created_by IS NULL
    """)
    op.alter_column("announcement", "created_by", nullable=False)
    op.create_foreign_key(
        "announcement_created_by_fkey",
        "announcement",
        "user",
        ["created_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_column("announcement", "ends_at")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for this migration")
