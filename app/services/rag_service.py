from __future__ import annotations

import asyncio
import logging
from typing import Any, List

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from ..clients.ollama_embeddings import EmbeddingClientError, embed_text
from ..config import get_settings
from ..database import create_session
from ..models import RagChunk

logger = logging.getLogger(__name__)
_settings = get_settings()


def _distance_filter_threshold() -> float:
    min_similarity = float(getattr(_settings, "rag_min_similarity", 0.3) or 0.3)
    min_similarity = max(0.0, min(1.0, min_similarity))
    return 1.0 - min_similarity  # cosine distance = 1 - cosine similarity


def _build_query(query_embedding: List[float]) -> Select:
    top_k = int(getattr(_settings, "rag_top_k", 4) or 4)
    distance_expr = RagChunk.embedding.cosine_distance(query_embedding).label("distance")
    stmt = (
        select(RagChunk, distance_expr)
        .order_by(distance_expr)
        .limit(top_k)
    )
    return stmt


def _run_similarity_query(query_embedding: List[float]) -> list[dict[str, Any]]:
    threshold = _distance_filter_threshold()
    session: Session = create_session()
    try:
        stmt = _build_query(query_embedding)
        rows = session.execute(stmt).all()
        results: list[dict[str, Any]] = []
        for chunk, distance in rows:
            if distance is None:
                continue
            if distance > threshold:
                continue
            results.append(
                {
                    "doc_id": str(chunk.doc_id),
                    "title": chunk.title,
                    "source": chunk.source,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "distance": float(distance),
                    "similarity": 1.0 - float(distance),
                }
            )
        return results
    finally:
        session.close()


async def query_similar_chunks(question: str) -> list[dict[str, Any]]:
    try:
        query_embedding = await embed_text(question)
    except EmbeddingClientError:
        logger.exception("Embedding failed for query")
        return []

    try:
        return await asyncio.to_thread(_run_similarity_query, query_embedding)
    except Exception:
        logger.exception("Similarity query failed")
        return []


__all__ = ["query_similar_chunks"]
