"""merge multiple heads

Revision ID: 63f6fc1df2cd
Revises: 20251220_add_rag_chunks, 7dbc1d05bd68
Create Date: 2025-12-12 17:33:33.579141

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '63f6fc1df2cd'
down_revision: Union[str, Sequence[str], None] = ('20251220_add_rag_chunks', '7dbc1d05bd68')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
