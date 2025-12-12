from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from ..config import get_settings
from ..database import Base

_settings = get_settings()
_VECTOR_DIM = int(getattr(_settings, "rag_embedding_dim", 3072) or 3072)


class RagChunk(Base):
    __tablename__ = "rag_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID(as_uuid=True), nullable=False)
    title = Column(Text, nullable=True)
    source = Column(String(255), nullable=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(128), nullable=False, unique=True)
    embedding = Column(Vector(dim=_VECTOR_DIM), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("doc_id", "chunk_index", name="uq_rag_chunks_doc_chunk"),
    )


__all__ = ["RagChunk"]
