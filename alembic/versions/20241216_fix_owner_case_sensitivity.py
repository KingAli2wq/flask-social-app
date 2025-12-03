"""Restrict owner promotion to the exact username case.

Revision ID: 20241216_fix_owner_case_sensitivity
Revises: 20241215_add_user_roles
Create Date: 2025-12-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20241216_fix_owner_case_sensitivity"
down_revision = "20241215_add_user_roles"
branch_labels = None
depends_on = None


OWNER_USERNAME = "Ali"

def upgrade() -> None:
    # Ensure only the canonical username receives owner privileges.
    op.execute(
        sa.text(
            """
            UPDATE users
            SET role = 'owner'
            WHERE username = :owner_username
            """
        ).bindparams(owner_username=OWNER_USERNAME)
    )

        # Demote other case-insensitive matches that were incorrectly promoted.
    op.execute(
        sa.text(
            """
            UPDATE users
                        SET role = 'user'
            WHERE username <> :owner_username
              AND lower(username) = lower(:owner_username)
              AND role = 'owner'
            """
        ).bindparams(owner_username=OWNER_USERNAME)
    )


def downgrade() -> None:
    # Cannot safely re-promote ambiguous usernames; no-op downgrade.
    pass
