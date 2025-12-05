"""Add avatar + encryption metadata to group chats.

Revision ID: 20251205_add_group_chat_security
Revises: 20241216_fix_owner_case_sensitivity
Create Date: 2025-12-05
"""
from __future__ import annotations

import secrets

from alembic import op
import sqlalchemy as sa
from cryptography.fernet import Fernet

# revision identifiers, used by Alembic.
revision = "20251205_add_group_chat_security"
down_revision = "20241216_fix_owner_case_sensitivity"
branch_labels = None
depends_on = None


LOCK_CONSTRAINT_NAME = "uq_group_chats_lock_code"


def upgrade() -> None:
    op.add_column("group_chats", sa.Column("avatar_url", sa.String(length=512), nullable=True))
    op.add_column("group_chats", sa.Column("lock_code", sa.String(length=128), nullable=True))
    op.add_column("group_chats", sa.Column("encryption_key", sa.String(length=128), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id FROM group_chats")).fetchall()
    for row in rows:
        chat_id = row[0]
        bind.execute(
            sa.text(
                """
                UPDATE group_chats
                SET lock_code = :lock_code,
                    encryption_key = :encryption_key
                WHERE id = :chat_id
                """
            ),
            {
                "lock_code": secrets.token_hex(24),
                "encryption_key": Fernet.generate_key().decode("utf-8"),
                "chat_id": chat_id,
            },
        )

    op.alter_column("group_chats", "lock_code", existing_type=sa.String(length=128), nullable=False)
    op.alter_column("group_chats", "encryption_key", existing_type=sa.String(length=128), nullable=False)
    op.create_unique_constraint(LOCK_CONSTRAINT_NAME, "group_chats", ["lock_code"])


def downgrade() -> None:
    op.drop_constraint(LOCK_CONSTRAINT_NAME, "group_chats", type_="unique")
    op.drop_column("group_chats", "encryption_key")
    op.drop_column("group_chats", "lock_code")
    op.drop_column("group_chats", "avatar_url")
