"""Merge group chat member roles + user DOB heads

Revision ID: 20260122_merge_group_chat_member_roles_and_user_dob
Revises: 20260109_add_group_chat_member_roles, 20260122_add_user_date_of_birth
Create Date: 2026-01-22

"""

from __future__ import annotations

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "20260122_merge_group_chat_member_roles_and_user_dob"
down_revision: Union[str, Sequence[str], None] = (
    "20260109_add_group_chat_member_roles",
    "20260122_add_user_date_of_birth",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
