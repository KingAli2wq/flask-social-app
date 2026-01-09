"""Merge missing 770aeba8e8aa with main head

Revision ID: 20260109_merge_770aeba8e8aa_and_main_head
Revises: 20260109_merge_language_preference_and_bans_heads, 770aeba8e8aa
Create Date: 2026-01-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260109_merge_770aeba8e8aa_and_main_head"
down_revision: Union[str, Sequence[str], None] = (
    "20260109_merge_language_preference_and_bans_heads",
    "770aeba8e8aa",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
