"""Add user ban fields.

Revision ID: 20260108_add_user_bans
Revises: 7dbc1d05bd68
Create Date: 2026-01-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260108_add_user_bans"
down_revision = "7dbc1d05bd68"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "users" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("users")}

    if "banned_at" not in columns:
        op.add_column("users", sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True))
    if "banned_until" not in columns:
        op.add_column("users", sa.Column("banned_until", sa.DateTime(timezone=True), nullable=True))
    if "ban_reason" not in columns:
        op.add_column("users", sa.Column("ban_reason", sa.String(length=500), nullable=True))
    if "banned_by" not in columns:
        op.add_column("users", sa.Column("banned_by", postgresql.UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "banned_by")
    op.drop_column("users", "ban_reason")
    op.drop_column("users", "banned_until")
    op.drop_column("users", "banned_at")
