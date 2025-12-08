"""Add stories table for ephemeral uploads."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql

# revision identifiers, used by Alembic.
revision: str = "f84e1de2c7ab"
down_revision: str = "20251205_add_group_chat_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stories",
        sa.Column("id", psql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", psql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "media_asset_id",
            psql.UUID(as_uuid=True),
            sa.ForeignKey("media_assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("media_url", sa.String(length=2048), nullable=False),
        sa.Column("media_content_type", sa.String(length=255), nullable=True),
        sa.Column("text_overlay", sa.String(length=280), nullable=True),
        sa.Column("text_color", sa.String(length=32), nullable=True),
        sa.Column("text_background", sa.String(length=120), nullable=True),
        sa.Column("text_position", sa.String(length=32), nullable=False, server_default="bottom-left"),
        sa.Column("text_font_size", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stories_user_id", "stories", ["user_id"])
    op.create_index("ix_stories_expires_at", "stories", ["expires_at"])
    op.create_index("ix_stories_media_asset_id", "stories", ["media_asset_id"])


def downgrade() -> None:
    op.drop_index("ix_stories_media_asset_id", table_name="stories")
    op.drop_index("ix_stories_expires_at", table_name="stories")
    op.drop_index("ix_stories_user_id", table_name="stories")
    op.drop_table("stories")
