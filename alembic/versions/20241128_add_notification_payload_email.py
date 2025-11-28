"""Add payload + emailed_at columns to notifications.

Revision ID: 7f1d8d2c9c01
Revises: e57c9c4de3fb
Create Date: 2025-11-28 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7f1d8d2c9c01"
down_revision = "e57c9c4de3fb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("payload", sa.JSON(), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("emailed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notifications", "emailed_at")
    op.drop_column("notifications", "payload")
