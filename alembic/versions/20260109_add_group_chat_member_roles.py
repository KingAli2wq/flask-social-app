"""Add member roles to group chats

Revision ID: 20260109_add_group_chat_member_roles
Revises: 20260109_merge_770aeba8e8aa_and_main_head
Create Date: 2026-01-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260109_add_group_chat_member_roles"
down_revision: Union[str, Sequence[str], None] = "20260109_merge_770aeba8e8aa_and_main_head"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "group_chat_members",
        sa.Column("role", sa.String(length=32), nullable=False, server_default=sa.text("'member'")),
    )

    # Mark existing group owners as leaders.
    op.execute(
        sa.text(
            """
            UPDATE group_chat_members
            SET role = 'leader'
            WHERE (group_chat_id, user_id) IN (
                SELECT id, owner_id FROM group_chats
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_column("group_chat_members", "role")
