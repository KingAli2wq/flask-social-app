"""Add post dislikes table.

Revision ID: 20241212_add_post_dislikes
Revises: 20241210_add_settings_email_verification
Create Date: 2025-12-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20241212_add_post_dislikes"
down_revision = "20241210_add_settings_email_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "post_dislikes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "user_id", name="uq_post_dislikes_post_user"),
    )
    op.create_index("ix_post_dislikes_post_id", "post_dislikes", ["post_id"])
    op.create_index("ix_post_dislikes_user_id", "post_dislikes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_post_dislikes_user_id", table_name="post_dislikes")
    op.drop_index("ix_post_dislikes_post_id", table_name="post_dislikes")
    op.drop_table("post_dislikes")
