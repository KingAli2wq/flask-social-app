"""Align media_assets table with current ORM model.

This migration is defensive: it adds missing columns and relaxes constraints
so MediaAsset inserts from ``upload_file_to_spaces`` succeed on existing databases.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as psql

# revision identifiers, used by Alembic.
revision: str = "1b0ef7a8d9f8"
down_revision: str = "9430f4be875b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table = "media_assets"

    # Create the table if it does not exist (matches current ORM shape).
    if not inspector.has_table(table):
        op.create_table(
            table,
            sa.Column("id", psql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", psql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("key", sa.String(length=1024), nullable=False),
            sa.Column("url", sa.String(length=2048), nullable=False),
            sa.Column("bucket", sa.String(length=255), nullable=False),
            sa.Column("content_type", sa.String(length=255), nullable=False),
            sa.Column("folder", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("key", name="uq_media_assets_key"),
        )
        op.create_index("ix_media_assets_user_id", table, ["user_id"])
        return

    # Add missing columns on existing deployments.
    existing_columns = {col["name"]: col for col in inspector.get_columns(table)}

    if "folder" not in existing_columns:
        op.add_column(table, sa.Column("folder", sa.String(length=255), nullable=True))

    if "bucket" not in existing_columns:
        op.add_column(table, sa.Column("bucket", sa.String(length=255), nullable=False, server_default=""))
        op.alter_column(table, "bucket", server_default=None)

    if "content_type" not in existing_columns:
        op.add_column(table, sa.Column("content_type", sa.String(length=255), nullable=False, server_default="application/octet-stream"))
        op.alter_column(table, "content_type", server_default=None)

    if "created_at" not in existing_columns:
        op.add_column(table, sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))

    # Ensure user_id is nullable to match ORM and allow uploads without a user context.
    user_col = existing_columns.get("user_id")
    if user_col and not user_col.get("nullable", True):
        op.alter_column(
            table,
            "user_id",
            existing_type=psql.UUID(as_uuid=True),
            nullable=True,
        )

    # Ensure key uniqueness if missing (harmless if already present).
    existing_uniques = {uc["name"] for uc in inspector.get_unique_constraints(table)}
    if "uq_media_assets_key" not in existing_uniques:
        op.create_unique_constraint("uq_media_assets_key", table, ["key"])

    existing_indexes = {idx["name"] for idx in inspector.get_indexes(table)}
    if "ix_media_assets_user_id" not in existing_indexes and "user_id" in existing_columns:
        op.create_index("ix_media_assets_user_id", table, ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table = "media_assets"

    if not inspector.has_table(table):
        return

    existing_indexes = {idx["name"] for idx in inspector.get_indexes(table)}
    if "ix_media_assets_user_id" in existing_indexes:
        op.drop_index("ix_media_assets_user_id", table_name=table)

    existing_uniques = {uc["name"] for uc in inspector.get_unique_constraints(table)}
    if "uq_media_assets_key" in existing_uniques:
        op.drop_constraint("uq_media_assets_key", table, type_="unique")

    existing_columns = {col["name"] for col in inspector.get_columns(table)}
    for col_name in ("folder", "bucket", "content_type", "created_at"):
        if col_name in existing_columns:
            op.drop_column(table, col_name)
