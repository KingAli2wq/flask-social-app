from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from dataclasses import dataclass
from typing import Iterable, List

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..clients.ollama_embeddings import EmbeddingClientError, embed_text
from ..config import get_settings
from ..database import create_session
from ..models import RagChunk

logger = logging.getLogger(__name__)
_settings = get_settings()


@dataclass(slots=True)
class EmbeddingChunk:
    doc_id: uuid.UUID
    title: str | None
    source: str | None
    chunk_index: int
    content: str


@dataclass(slots=True)
class EmbeddingJob:
    doc_id: uuid.UUID
    chunks: list[EmbeddingChunk]


_queue: asyncio.Queue[EmbeddingJob] = asyncio.Queue()
_worker_task: asyncio.Task[None] | None = None
_worker_running = False


def _chunk_text(text: str) -> list[str]:
    size = max(100, int(getattr(_settings, "rag_chunk_size_chars", 1000) or 1000))
    overlap = max(0, int(getattr(_settings, "rag_chunk_overlap_chars", 150) or 150))
    if overlap >= size:
        overlap = max(0, size // 3)
    value = (text or "").strip()
    if not value:
        return []
    chunks: list[str] = []
    start = 0
    length = len(value)
    while start < length:
        end = min(length, start + size)
        chunk = value[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = end - overlap if overlap > 0 else end
        if start < 0:
            start = 0
        if start >= length:
            break
    return chunks


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def enqueue_document_ingestion(*, title: str | None, source: str | None, text: str) -> tuple[uuid.UUID, int]:
    doc_id = uuid.uuid4()
    chunks = _chunk_text(text)
    job = EmbeddingJob(
        doc_id=doc_id,
        chunks=[
            EmbeddingChunk(doc_id=doc_id, title=title, source=source, chunk_index=idx, content=chunk)
            for idx, chunk in enumerate(chunks)
        ],
    )
    await _queue.put(job)
    return doc_id, len(job.chunks)


def _persist_chunk(job_chunk: EmbeddingChunk, embedding: List[float]) -> None:
    session = create_session()
    try:
        instance = RagChunk(
            doc_id=job_chunk.doc_id,
            title=job_chunk.title,
            source=job_chunk.source,
            chunk_index=job_chunk.chunk_index,
            content=job_chunk.content,
            content_hash=_hash_content(job_chunk.content),
            embedding=embedding,
        )
        session.add(instance)
        session.commit()
    except IntegrityError:
        session.rollback()
        logger.info("Duplicate chunk skipped for doc %s index=%s", job_chunk.doc_id, job_chunk.chunk_index)
    except SQLAlchemyError:
        session.rollback()
        logger.exception("Failed to persist chunk doc=%s index=%s", job_chunk.doc_id, job_chunk.chunk_index)
        raise
    finally:
        session.close()


async def _process_job(job: EmbeddingJob) -> None:
    for chunk in job.chunks:
        try:
            embedding = await embed_text(chunk.content)
        except EmbeddingClientError:
            logger.exception("Embedding generation failed for doc=%s index=%s", job.doc_id, chunk.chunk_index)
            continue
        try:
            await asyncio.to_thread(_persist_chunk, chunk, embedding)
        except Exception:
            logger.exception("Persist chunk failed for doc=%s index=%s", job.doc_id, chunk.chunk_index)
            continue


async def _worker_loop() -> None:
    global _worker_running
    _worker_running = True
    try:
        while True:
            job = await _queue.get()
            try:
                await _process_job(job)
            finally:
                _queue.task_done()
    except asyncio.CancelledError:  # pragma: no cover - shutdown path
        logger.info("Embedding worker cancelled")
    finally:
        _worker_running = False


async def start_embedding_worker() -> None:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop())
        logger.info("Embedding worker started")


def get_queue_status() -> dict[str, object]:
    return {
        "pending": _queue.qsize(),
        "running": bool(_worker_running),
    }


async def shutdown_embedding_worker() -> None:
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass


__all__ = [
    "enqueue_document_ingestion",
    "get_queue_status",
    "start_embedding_worker",
    "shutdown_embedding_worker",
]
