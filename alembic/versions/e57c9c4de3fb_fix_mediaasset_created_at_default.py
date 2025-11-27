"""Fix created_at default on media_assets"""

from alembic import op
import sqlalchemy as sa

revision = "e57c9c4de3fb"
down_revision = "20241120_add_bio_media_asset"

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
