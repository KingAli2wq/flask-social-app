"""Merge chatbot and stories heads.

Revision ID: 20251217_merge_chatbot_and_stories_heads
Revises: 20251208_add_ai_chatbot_tables, f84e1de2c7ab
Create Date: 2025-12-09
"""
from __future__ import annotations

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "20251217_merge_chatbot_and_stories_heads"
down_revision: Union[str, Sequence[str], None] = (
    "20251208_add_ai_chatbot_tables",
    "f84e1de2c7ab",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No schema changes; this revision exists solely to merge divergent heads.
    pass


def downgrade() -> None:
    # Downgrade would reintroduce the split heads, so leave as no-op.
    pass
