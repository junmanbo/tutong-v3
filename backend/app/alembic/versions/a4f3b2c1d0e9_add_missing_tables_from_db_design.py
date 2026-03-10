"""add missing tables from db design doc

Revision ID: a4f3b2c1d0e9
Revises: c9d8e7f6a5b4
Create Date: 2026-03-09 23:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a4f3b2c1d0e9"
down_revision: Union[str, None] = "c9d8e7f6a5b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usersession",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=255), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash"),
    )

    op.create_table(
        "paymenthistory",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=True),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("amount_krw", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("pg_provider", sa.String(length=50), nullable=True),
        sa.Column("pg_payment_id", sa.String(length=255), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subscription_id"], ["usersubscription.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_id"], ["subscriptionplan.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pg_payment_id"),
    )

    op.create_table(
        "botconfiggrid",
        sa.Column("bot_id", sa.Uuid(), nullable=False),
        sa.Column("upper_price", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("lower_price", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("grid_count", sa.Integer(), nullable=False),
        sa.Column("grid_type", sa.String(length=20), nullable=False),
        sa.Column("quantity_per_grid", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("bot_id"),
    )

    op.create_table(
        "botconfigsnowball",
        sa.Column("bot_id", sa.Uuid(), nullable=False),
        sa.Column("initial_amount", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("drop_trigger_pct", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("max_layers", sa.Integer(), nullable=False),
        sa.Column("multiplier", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("take_profit_pct", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("current_layer", sa.Integer(), nullable=False),
        sa.Column("avg_entry_price", sa.Numeric(precision=36, scale=18), nullable=True),
        sa.Column("total_invested", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("bot_id"),
    )

    op.create_table(
        "botconfigrebalancing",
        sa.Column("bot_id", sa.Uuid(), nullable=False),
        sa.Column("rebal_mode", sa.String(length=30), nullable=False),
        sa.Column("interval_unit", sa.String(length=20), nullable=True),
        sa.Column("interval_value", sa.Integer(), nullable=True),
        sa.Column("deviation_threshold_pct", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("last_rebalanced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("bot_id"),
    )

    op.create_table(
        "botconfigrebalasset",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bot_id", sa.Uuid(), nullable=False),
        sa.Column("asset_symbol", sa.String(length=20), nullable=False),
        sa.Column("target_weight_pct", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("current_weight_pct", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_id", "asset_symbol", name="uq_botconfigrebalasset_bot_asset"),
    )

    op.create_table(
        "botconfigdca",
        sa.Column("bot_id", sa.Uuid(), nullable=False),
        sa.Column("order_amount", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("interval_unit", sa.String(length=20), nullable=False),
        sa.Column("interval_value", sa.Integer(), nullable=False),
        sa.Column("total_orders", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("bot_id"),
    )

    op.create_table(
        "botconfigalgo",
        sa.Column("bot_id", sa.Uuid(), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("slices", sa.Integer(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("order_type", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("bot_id"),
    )

    op.create_table(
        "botorder",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bot_id", sa.Uuid(), nullable=False),
        sa.Column("exchange_order_id", sa.String(length=255), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("order_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("price", sa.Numeric(precision=36, scale=18), nullable=True),
        sa.Column("avg_fill_price", sa.Numeric(precision=36, scale=18), nullable=True),
        sa.Column("filled_quantity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("fee", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("fee_currency", sa.String(length=20), nullable=True),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_botorder_exchange_order_id", "botorder", ["exchange_order_id"], unique=False)
    op.create_index("ix_botorder_bot_id_placed_at", "botorder", ["bot_id", "placed_at"], unique=False)

    op.create_table(
        "bottrade",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bot_order_id", sa.Uuid(), nullable=False),
        sa.Column("bot_id", sa.Uuid(), nullable=False),
        sa.Column("exchange_trade_id", sa.String(length=255), nullable=True),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("price", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("amount", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("fee", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("fee_currency", sa.String(length=20), nullable=True),
        sa.Column("traded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bot_order_id"], ["botorder.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bot_id"], ["bot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bottrade_bot_id_traded_at", "bottrade", ["bot_id", "traded_at"], unique=False)

    op.create_table(
        "botsnapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bot_id", sa.Uuid(), nullable=False),
        sa.Column("total_equity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("cash_balance", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("positions_value", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("total_pnl", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("total_pnl_pct", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_botsnapshot_bot_id_snapshot_at", "botsnapshot", ["bot_id", "snapshot_at"], unique=False)

    op.create_table(
        "announcement",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("announcement")

    op.drop_index("ix_botsnapshot_bot_id_snapshot_at", table_name="botsnapshot")
    op.drop_table("botsnapshot")

    op.drop_index("ix_bottrade_bot_id_traded_at", table_name="bottrade")
    op.drop_table("bottrade")

    op.drop_index("ix_botorder_bot_id_placed_at", table_name="botorder")
    op.drop_index("ix_botorder_exchange_order_id", table_name="botorder")
    op.drop_table("botorder")

    op.drop_table("botconfigalgo")
    op.drop_table("botconfigdca")
    op.drop_table("botconfigrebalasset")
    op.drop_table("botconfigrebalancing")
    op.drop_table("botconfigsnowball")
    op.drop_table("botconfiggrid")

    op.drop_table("paymenthistory")
    op.drop_table("usersession")
