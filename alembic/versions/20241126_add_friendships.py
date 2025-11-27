"""add friend request and friendship tables

Revision ID: 20241126_add_friendships
Revises: e57c9c4de3fb
Create Date: 2025-11-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20241126_add_friendships"
down_revision = "e57c9c4de3fb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    friend_request_status = sa.Enum("pending", "accepted", "declined", name="friend_request_status")
    friend_request_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "friend_requests",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("sender_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", friend_request_status, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("sender_id", "recipient_id", name="uq_friend_request_pair"),
    )
    op.create_index("ix_friend_requests_sender_id", "friend_requests", ["sender_id"])
    op.create_index("ix_friend_requests_recipient_id", "friend_requests", ["recipient_id"])

    op.create_table(
        "friendships",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_a_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_b_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("thread_id", sa.String(length=96), nullable=False),
        sa.Column("lock_code", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("thread_id", name="uq_friendships_thread"),
        sa.UniqueConstraint("lock_code", name="uq_friendships_lock"),
        sa.UniqueConstraint("user_a_id", "user_b_id", name="uq_friendship_pair"),
    )
    op.create_index("ix_friendships_user_a_id", "friendships", ["user_a_id"])
    op.create_index("ix_friendships_user_b_id", "friendships", ["user_b_id"])


def downgrade() -> None:
    op.drop_index("ix_friendships_user_b_id", table_name="friendships")
    op.drop_index("ix_friendships_user_a_id", table_name="friendships")
    op.drop_table("friendships")

    op.drop_index("ix_friend_requests_recipient_id", table_name="friend_requests")
    op.drop_index("ix_friend_requests_sender_id", table_name="friend_requests")
    op.drop_table("friend_requests")

    friend_request_status = sa.Enum("pending", "accepted", "declined", name="friend_request_status")
    friend_request_status.drop(op.get_bind(), checkfirst=True)
