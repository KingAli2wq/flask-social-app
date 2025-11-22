"""Fix created_at default on media_assets"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "<put new revision ID here>"
down_revision = "e243ab1ae13a"   # This is your current head
branch_labels = None
depends_on = None

def upgrade():
    # Add default if missing
    op.alter_column(
        "media_assets",
        "created_at",
        server_default=sa.text("NOW()"),
        existing_type=sa.DateTime(timezone=True),
        nullable=False
    )

def downgrade():
    # Reverse only the default — keep NOT NULL as-is
    op.alter_column(
        "media_assets",
        "created_at",
        server_default=None,
        existing_type=sa.DateTime(timezone=True),
        nullable=False
    )
