"""Merge new engagement branch

Revision ID: 1fe29d00399b
Revises: 7f1d8d2c9c01, 20241208_add_post_engagement_and_message_replies
Create Date: 2025-11-28 17:35:34.026394
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "1fe29d00399b"

# The REAL two heads before the duplicate merge files were created
down_revision: Union[str, Sequence[str], None] = (
    "7f1d8d2c9c01",
    "20241208_add_post_engagement_and_message_replies",
)

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

