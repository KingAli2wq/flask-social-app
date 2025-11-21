"""Pydantic schemas for post resources backed by PostgreSQL."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PostCreate(BaseModel):
    """Payload used by API clients when constructing a post."""

    content: str = Field(..., min_length=1, max_length=280)
    user_id: UUID
    media_url: str | None = None
    media_asset_id: UUID | None = None


class PostResponse(BaseModel):
    """Serialized representation of a persisted post."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    content: str
    media_url: str | None = None
    media_asset_id: UUID | None = None
    created_at: datetime


class PostFeedResponse(BaseModel):
    """Envelope used when returning a collection of posts."""

    items: list[PostResponse]


__all__ = ["PostCreate", "PostResponse", "PostFeedResponse"]
