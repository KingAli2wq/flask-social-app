from __future__ import annotations

from pydantic import BaseModel, Field


class RagIngestRequest(BaseModel):
    title: str | None = Field(None, description="Optional title for the document")
    source: str | None = Field(None, description="Source identifier, e.g. url or filename")
    text: str = Field(..., min_length=1, description="Raw text content to chunk and embed")


class RagQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question to embed and search against stored chunks")


__all__ = ["RagIngestRequest", "RagQueryRequest"]
