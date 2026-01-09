"""Add language preference to users.

Revision ID: 20251220_add_language_preference_to_users
Revises: 20251217_merge_chatbot_and_stories_heads
Create Date: 2025-12-10
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "20251220_add_language_preference_to_users"
down_revision = "20251217_merge_chatbot_and_stories_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "users" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("users")}

    if "language_preference" not in columns:
        op.add_column(
            "users",
            sa.Column("language_preference", sa.String(length=16), nullable=True, server_default="en"),
        )

    # Safe even if the column already existed.
    op.execute(sa.text("UPDATE users SET language_preference = 'en' WHERE language_preference IS NULL"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "users" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("users")}
    if "language_preference" in columns:
        op.drop_column("users", "language_preference")
