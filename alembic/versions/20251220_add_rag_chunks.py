"""add rag chunks table and pgvector extension

Revision ID: 20251220_add_rag_chunks
Revises: 20251217_merge_chatbot_and_stories_heads
Create Date: 2025-12-20 00:00:00.000000
"""

from __future__ import annotations

import os
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "20251220_add_rag_chunks"
down_revision: str | None = "20251217_merge_chatbot_and_stories_heads"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _embedding_dim() -> int:
    """
    pgvector ANN indexes (ivfflat/hnsw) on the `vector` type require <= 2000 dims.
    Default to 768 for broad compatibility.
    """
    try:
        dim = int(os.getenv("RAG_EMBEDDING_DIM", "768"))
    except ValueError:
        dim = 768

    if dim <= 0:
        return 768
    if dim > 2000:
        return 2000
    return dim


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "rag_chunks",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("doc_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("embedding", Vector(dim=_embedding_dim()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("doc_id", "chunk_index", name="uq_rag_chunks_doc_chunk"),
    )

    op.create_index("ix_rag_chunks_doc_id", "rag_chunks", ["doc_id"])
    op.create_index("ix_rag_chunks_source", "rag_chunks", ["source"])

    # Vector similarity index (cosine).
    # If HNSW is unavailable on your pgvector build, replace with:
    # op.execute(
    #   "CREATE INDEX IF NOT EXISTS ix_rag_chunks_embedding "
    #   "ON rag_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    # )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_rag_chunks_embedding "
        "ON rag_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_rag_chunks_embedding;")
    op.drop_index("ix_rag_chunks_source", table_name="rag_chunks")
    op.drop_index("ix_rag_chunks_doc_id", table_name="rag_chunks")
    op.drop_table("rag_chunks")

