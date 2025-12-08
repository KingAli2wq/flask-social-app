"""Pydantic schemas for ephemeral stories."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class StoryCreate(BaseModel):
    media_asset_id: UUID
    text_overlay: str | None = Field(default=None, max_length=280)
    text_color: str | None = Field(default=None, max_length=32)
    text_background: str | None = Field(default=None, max_length=120)
    text_position: str | None = Field(default=None, max_length=32)
    text_font_size: int | None = Field(default=None, ge=12, le=48)


class StoryItem(BaseModel):
    id: UUID
    media_url: str
    media_content_type: str | None = None
    text_overlay: str | None = None
    text_color: str | None = None
    text_background: str | None = None
    text_position: str | None = None
    text_font_size: int | None = None
    created_at: datetime
    expires_at: datetime


class StoryAuthor(BaseModel):
    id: UUID
    username: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None


class StoryBucket(BaseModel):
    user: StoryAuthor
    stories: list[StoryItem]


class StoryFeedResponse(BaseModel):
    items: list[StoryBucket]


__all__ = [
    "StoryCreate",
    "StoryItem",
    "StoryAuthor",
    "StoryBucket",
    "StoryFeedResponse",
]
