from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ..config import get_settings
from ..schemas.rag import RagIngestRequest, RagQueryRequest
from ..services import (
    enqueue_document_ingestion,
    get_current_user,
    get_queue_status,
    query_similar_chunks,
    start_embedding_worker,
)

router = APIRouter(prefix="/rag", tags=["rag"])
logger = logging.getLogger(__name__)
_settings = get_settings()


def _ensure_enabled() -> None:
    if not getattr(_settings, "rag_enabled", False):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="RAG is disabled")


@router.post("/ingest")
async def ingest_document(payload: RagIngestRequest, user=Depends(get_current_user)) -> dict[str, object]:
    _ensure_enabled()
    if not payload.text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="text is required")

    await start_embedding_worker()
    doc_id, chunk_count = await enqueue_document_ingestion(
        title=payload.title,
        source=payload.source,
        text=payload.text,
    )
    logger.info("RAG ingest enqueued | user=%s doc=%s chunks=%s", user.id, doc_id, chunk_count)
    return {"doc_id": str(doc_id), "chunks_enqueued": chunk_count}


@router.post("/query")
async def query_rag(payload: RagQueryRequest, user=Depends(get_current_user)) -> dict[str, object]:
    _ensure_enabled()
    results = await query_similar_chunks(payload.question)
    logger.info("RAG query | user=%s results=%s", user.id, len(results))
    return {"results": results}


@router.get("/status")
async def rag_status(user=Depends(get_current_user)) -> dict[str, object]:
    _ensure_enabled()
    return get_queue_status()
