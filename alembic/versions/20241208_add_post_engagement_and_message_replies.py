"""Add likes/comments tables and message reply metadata.

Revision ID: 20241208_add_post_engagement_and_message_replies
Revises: 20241207_add_follows_table
Create Date: 2025-11-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20241208_add_post_engagement_and_message_replies"
down_revision = "20241207_add_follows_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "post_likes",
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
        sa.UniqueConstraint("post_id", "user_id", name="uq_post_likes_post_user"),
    )
    op.create_index("ix_post_likes_post_id", "post_likes", ["post_id"])
    op.create_index("ix_post_likes_user_id", "post_likes", ["user_id"])

    op.create_table(
        "post_comments",
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
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("post_comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_post_comments_post_id", "post_comments", ["post_id"])
    op.create_index("ix_post_comments_user_id", "post_comments", ["user_id"])
    op.create_index("ix_post_comments_parent_id", "post_comments", ["parent_id"])

    op.add_column("messages", sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "messages",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("messages", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_messages_parent_id", "messages", ["parent_id"])
    op.create_foreign_key(
        "fk_messages_parent_id_messages",
        "messages",
        "messages",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_messages_parent_id_messages", "messages", type_="foreignkey")
    op.drop_index("ix_messages_parent_id", table_name="messages")
    op.drop_column("messages", "deleted_at")
    op.drop_column("messages", "is_deleted")
    op.drop_column("messages", "parent_id")

    op.drop_index("ix_post_comments_parent_id", table_name="post_comments")
    op.drop_index("ix_post_comments_user_id", table_name="post_comments")
    op.drop_index("ix_post_comments_post_id", table_name="post_comments")
    op.drop_table("post_comments")

    op.drop_index("ix_post_likes_user_id", table_name="post_likes")
    op.drop_index("ix_post_likes_post_id", table_name="post_likes")
    op.drop_table("post_likes")
