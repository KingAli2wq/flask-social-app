"""merge all heads

Revision ID: 7dbc1d05bd68
Revises: 20251219_add_status_to_ai_chat_sessions, 20251220_add_support_tickets_table, 698bdf0efe08
Create Date: 2025-12-11 00:30:11.209967

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7dbc1d05bd68'
down_revision: Union[str, Sequence[str], None] = ('20251219_add_status_to_ai_chat_sessions', '20251220_add_support_tickets_table', '698bdf0efe08')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
