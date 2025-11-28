"""Merge notification payload and engagement branches.

Revision ID: 20241209_merge_notification_and_engagement_heads
Revises: 7f1d8d2c9c01, 20241208_add_post_engagement_and_message_replies
Create Date: 2025-11-28 17:40:00
"""
from __future__ import annotations

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


# revision identifiers, used by Alembic.
revision = "20241209_merge_notification_and_engagement_heads"
down_revision = ("7f1d8d2c9c01", "20241208_add_post_engagement_and_message_replies")
branch_labels = None
depends_on = None


def upgrade() -> None:  # pragma: no cover - no-op merge
    pass


def downgrade() -> None:  # pragma: no cover - no-op merge
    pass
