"""add rag chunks table and pgvector extension

Revision ID: 20251220_add_rag_chunks
Revises: 20251217_merge_chatbot_and_stories_heads
Create Date: 2025-12-20 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = "20251220_add_rag_chunks"
down_revision: str | None = "20251217_merge_chatbot_and_stories_heads"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    dim = 3072
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS rag_chunks (
            id UUID PRIMARY KEY,
            doc_id UUID NOT NULL,
            title TEXT NULL,
            source VARCHAR(255) NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            content_hash VARCHAR(128) NOT NULL UNIQUE,
            embedding vector({dim}) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_rag_chunks_doc_chunk UNIQUE (doc_id, chunk_index)
        );
        CREATE INDEX IF NOT EXISTS ix_rag_chunks_embedding ON rag_chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rag_chunks CASCADE;")
