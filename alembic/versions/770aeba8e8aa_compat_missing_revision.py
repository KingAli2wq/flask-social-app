"""Compat: missing revision 770aeba8e8aa

This is a compatibility placeholder for a production database that was stamped
with revision `770aeba8e8aa`, but where the corresponding migration script is
not present in this repository.

Revision ID: 770aeba8e8aa
Revises: 7dbc1d05bd68
Create Date: 2026-01-09

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "770aeba8e8aa"
down_revision = "7dbc1d05bd68"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
