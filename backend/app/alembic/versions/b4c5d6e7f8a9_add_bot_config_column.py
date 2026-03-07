"""add_bot_config_column

Revision ID: b4c5d6e7f8a9
Revises: 3a8f2e4b7c11
Create Date: 2026-03-07 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b4c5d6e7f8a9"
down_revision = "f7c1a2d9b4ef"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "bot",
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("bot", "config")
