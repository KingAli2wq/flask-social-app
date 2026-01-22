"""Add date_of_birth to users

Revision ID: 20260122_add_user_date_of_birth
Revises: 20260109_merge_770aeba8e8aa_and_main_head
Create Date: 2026-01-22

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260122_add_user_date_of_birth"
down_revision: Union[str, Sequence[str], None] = "20260109_merge_770aeba8e8aa_and_main_head"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "date_of_birth")
