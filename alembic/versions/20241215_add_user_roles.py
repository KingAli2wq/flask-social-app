"""Add user roles and promote owner account.

Revision ID: 20241215_add_user_roles
Revises: 20241213_add_media_engagement_tables
Create Date: 2025-12-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20241215_add_user_roles"
down_revision = "20241213_add_media_engagement_tables"
branch_labels = None
depends_on = None


OWNER_USERNAME = "Ali"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=32),
            nullable=False,
            server_default="user",
        ),
    )
    op.create_index("ix_users_role", "users", ["role"])
    op.execute(
        sa.text(
            """
            UPDATE users
            SET role = 'owner'
            WHERE lower(username) = lower(:owner_username)
            """
        ).bindparams(owner_username=OWNER_USERNAME)
    )


def downgrade() -> None:
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "role")
