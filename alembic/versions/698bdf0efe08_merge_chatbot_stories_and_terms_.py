"""merge chatbot/stories and terms acceptance branches

Revision ID: 698bdf0efe08
Revises: 20251217_merge_chatbot_and_stories_heads, 20241124_add_terms_acceptance
Create Date: 2025-12-10 20:02:48.525937

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '698bdf0efe08'
down_revision: Union[str, Sequence[str], None] = ('20251217_merge_chatbot_and_stories_heads', '20241124_add_terms_acceptance')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
