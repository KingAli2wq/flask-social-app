"""Add user settings and email verification columns.

Revision ID: 20241210_add_settings_email_verification
Revises: 20241209_merge_notification_and_engagement_heads
Create Date: 2025-11-28 18:50:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20241210_add_settings_email_verification"
down_revision = "1fe29d00399b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(length=150), nullable=True))
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("email_verification_code", sa.String(length=12), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_verification_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "email_dm_notifications",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "allow_friend_requests",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "dm_followers_only",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "dm_followers_only")
    op.drop_column("users", "allow_friend_requests")
    op.drop_column("users", "email_dm_notifications")
    op.drop_column("users", "email_verification_sent_at")
    op.drop_column("users", "email_verification_code")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "display_name")
