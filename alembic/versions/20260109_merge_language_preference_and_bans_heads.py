"""Merge language preference + bans heads

Revision ID: 20260109_merge_language_preference_and_bans_heads
Revises: 20260108_add_user_bans, 20251220_add_language_preference_to_users
Create Date: 2026-01-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260109_merge_language_preference_and_bans_heads"
down_revision: Union[str, Sequence[str], None] = (
    "20260108_add_user_bans",
    "20251220_add_language_preference_to_users",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
