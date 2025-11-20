"""Pydantic schemas for post resources."""
from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=280)
    attachments: List[str] = Field(default_factory=list)


class PostResponse(BaseModel):
    id: str
    author: str
    content: str
    attachments: List[str]
    created_at: datetime
    updated_at: datetime | None
    likes: int
    dislikes: int


class PostFeedResponse(BaseModel):
    items: List[PostResponse]


__all__ = ["PostCreate", "PostResponse", "PostFeedResponse"]
