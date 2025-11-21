"""Add bio to users and media_asset_id to posts.

Revision ID: 20241120_add_bio_media_asset
Revises: None
Create Date: 2025-11-20
"""
from __future__ import annotations

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20241120_add_bio_media_asset"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the schema changes."""

    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column(
        "posts",
        sa.Column(
            "media_asset_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Revert the schema changes."""

    op.drop_column("posts", "media_asset_id")
    op.drop_column("users", "bio")
