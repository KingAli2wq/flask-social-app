"""Allow non-UUID chat identifiers for direct messages.

Switches the messages.chat_id column to VARCHAR so friendship thread
identifiers (hex strings) can be persisted without casting errors.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20241203_change_messages_chat_id_to_string"
down_revision = "20241126_add_friendships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Promote messages.chat_id to VARCHAR for mixed thread identifiers."""

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite / test databases already store chat_id as TEXT via ORM metadata.
        return

    op.alter_column(
        "messages",
        "chat_id",
        existing_type=postgresql.UUID(),
        type_=sa.String(length=128),
        existing_nullable=True,
        postgresql_using="chat_id::text",
    )


def downgrade() -> None:
    """Revert chat_id back to UUID, nulling non-UUID identifiers."""

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.alter_column(
        "messages",
        "chat_id",
        existing_type=sa.String(length=128),
        type_=postgresql.UUID(),
        existing_nullable=True,
        postgresql_using=(
            "CASE "
            "WHEN chat_id ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' "
            "THEN chat_id::uuid "
            "ELSE NULL "
            "END"
        ),
    )
