"""Add terms acceptance tracking columns to users.

Revision ID: 20241124_add_terms_acceptance
Revises: 1b0ef7a8d9f8
Create Date: 2024-11-24
"""
from __future__ import annotations

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20241124_add_terms_acceptance"
down_revision = "1b0ef7a8d9f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply schema changes."""

    op.add_column("users", sa.Column("accepted_terms_version", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Revert schema changes."""

    op.drop_column("users", "terms_accepted_at")
    op.drop_column("users", "accepted_terms_version")
