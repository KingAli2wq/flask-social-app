"""Merge new engagement branch

Revision ID: 1fe29d00399b
Revises: 08bd1470d6b3, 20241209_merge_notification_and_engagement_heads
Create Date: 2025-11-28 17:35:34.026394

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1fe29d00399b'
down_revision: Union[str, Sequence[str], None] = ('08bd1470d6b3', '20241209_merge_notification_and_engagement_heads')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
