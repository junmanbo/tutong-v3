"""add_bot_log_table

Revision ID: 3a8f2e4b7c11
Revises: 758de2786634
Create Date: 2026-03-07 18:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "3a8f2e4b7c11"
down_revision = "758de2786634"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "botlog",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bot_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_botlog_bot_id_created_at",
        "botlog",
        ["bot_id", "created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_botlog_bot_id_created_at", table_name="botlog")
    op.drop_table("botlog")

