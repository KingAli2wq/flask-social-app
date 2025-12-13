"""drop rag chunks table and remove vector extension when unused

Revision ID: 20251221_drop_rag_chunks
Revises: 20251220_add_rag_chunks
Create Date: 2025-12-21 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = "20251221_drop_rag_chunks"
down_revision: str | None = "20251220_add_rag_chunks"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rag_chunks CASCADE;")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
                -- Check for remaining vector-typed columns; drop extension only if none exist.
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_attribute a
                    JOIN pg_class c ON a.attrelid = c.oid
                    JOIN pg_type t ON a.atttypid = t.oid
                    WHERE t.typname = 'vector'
                      AND c.relkind = 'r'
                      AND a.attnum > 0
                      AND NOT a.attisdropped
                ) THEN
                    EXECUTE 'DROP EXTENSION IF EXISTS vector';
                END IF;
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_chunks (
            id UUID PRIMARY KEY,
            doc_id UUID NOT NULL,
            title TEXT NULL,
            source VARCHAR(255) NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            content_hash VARCHAR(128) NOT NULL UNIQUE,
            embedding vector NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_rag_chunks_doc_chunk UNIQUE (doc_id, chunk_index)
        );
        CREATE INDEX IF NOT EXISTS ix_rag_chunks_embedding ON rag_chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
        """
    )
