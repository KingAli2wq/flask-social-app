"""Add status column to AI chat sessions.

Revision ID: 20251219_add_status_to_ai_chat_sessions
Revises: 20251217_merge_chatbot_and_stories_heads
Create Date: 2025-12-10
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251219_add_status_to_ai_chat_sessions"
down_revision = "20251217_merge_chatbot_and_stories_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_chat_sessions",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
    )
    # Ensure existing rows adopt the new default state and avoid lingering "preparing" markers.
    op.execute(
        "UPDATE ai_chat_sessions SET status = 'active' "
        "WHERE status IS NULL OR status = '' OR status = 'preparing'"
    )


def downgrade() -> None:
    op.drop_column("ai_chat_sessions", "status")
