"""Add media engagement tables for likes, dislikes, and comments.

Revision ID: 20241213_add_media_engagement_tables
Revises: 20241212_add_post_dislikes
Create Date: 2025-12-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20241213_add_media_engagement_tables"
down_revision = "20241212_add_post_dislikes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_likes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "media_asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_assets.id", ondelete="CASCADE"),
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
        sa.UniqueConstraint("media_asset_id", "user_id", name="uq_media_likes_asset_user"),
    )
    op.create_index("ix_media_likes_media_asset_id", "media_likes", ["media_asset_id"])
    op.create_index("ix_media_likes_user_id", "media_likes", ["user_id"])

    op.create_table(
        "media_dislikes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "media_asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_assets.id", ondelete="CASCADE"),
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
        sa.UniqueConstraint("media_asset_id", "user_id", name="uq_media_dislikes_asset_user"),
    )
    op.create_index("ix_media_dislikes_media_asset_id", "media_dislikes", ["media_asset_id"])
    op.create_index("ix_media_dislikes_user_id", "media_dislikes", ["user_id"])

    op.create_table(
        "media_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "media_asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_comments_media_asset_id", "media_comments", ["media_asset_id"])
    op.create_index("ix_media_comments_user_id", "media_comments", ["user_id"])
    op.create_index("ix_media_comments_parent_id", "media_comments", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_media_comments_parent_id", table_name="media_comments")
    op.drop_index("ix_media_comments_user_id", table_name="media_comments")
    op.drop_index("ix_media_comments_media_asset_id", table_name="media_comments")
    op.drop_table("media_comments")

    op.drop_index("ix_media_dislikes_user_id", table_name="media_dislikes")
    op.drop_index("ix_media_dislikes_media_asset_id", table_name="media_dislikes")
    op.drop_table("media_dislikes")

    op.drop_index("ix_media_likes_user_id", table_name="media_likes")
    op.drop_index("ix_media_likes_media_asset_id", table_name="media_likes")
    op.drop_table("media_likes")
