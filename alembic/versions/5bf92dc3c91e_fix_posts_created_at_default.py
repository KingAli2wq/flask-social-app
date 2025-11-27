"""Fix created_at default on posts table"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = "5bf92dc3c91e"
down_revision = "2c4f9c2c4d6b"
branch_labels = None
depends_on = None


def upgrade():
    # Ensure posts.created_at has server default NOW()
    op.alter_column(
        "posts",
        "created_at",
        server_default=sa.text("NOW()"),
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade():
    # Remove the default (keep NOT NULL)
    op.alter_column(
        "posts",
        "created_at",
        server_default=None,
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
