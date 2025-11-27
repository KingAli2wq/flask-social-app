"""Ensure messages.created_at uses server-side timestamp.

Existing rows already have values, but inserts were failing because the
column lacked a default. This migration aligns the database column with
our ORM definition (`server_default=func.now()`).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20241204_set_messages_created_at_default"
down_revision = "20241203_change_messages_chat_id_to_string"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "messages",
        "created_at",
        server_default=sa.text("NOW()"),
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "messages",
        "created_at",
        server_default=None,
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
