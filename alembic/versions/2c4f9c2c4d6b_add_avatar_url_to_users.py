"""Add avatar_url to users for profile images."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "2c4f9c2c4d6b"
down_revision = "1b0ef7a8d9f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table = "users"
    existing_columns = {col["name"] for col in inspector.get_columns(table)}
    if "avatar_url" not in existing_columns:
        op.add_column(table, sa.Column("avatar_url", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table = "users"
    existing_columns = {col["name"] for col in inspector.get_columns(table)}
    if "avatar_url" in existing_columns:
        op.drop_column(table, "avatar_url")
