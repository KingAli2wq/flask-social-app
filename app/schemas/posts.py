"""Pydantic schemas for post resources backed by PostgreSQL."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PostCreate(BaseModel):
    """Payload used by API clients when constructing a post."""

    caption: str = Field(..., min_length=1, max_length=280)
    user_id: UUID
    media_url: str | None = None
    media_asset_id: UUID | None = None


class PostResponse(BaseModel):
    """Serialized representation of a persisted post."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    caption: str
    media_url: str | None = None
    media_asset_id: UUID | None = None
    media_content_type: str | None = None
    created_at: datetime
    username: str | None = None
    avatar_url: str | None = None
    author_role: str | None = None
    follow_priority: int | None = None
    is_following_author: bool | None = None
    like_count: int = 0
    dislike_count: int = 0
    comment_count: int = 0
    viewer_has_liked: bool = False
    viewer_has_disliked: bool = False


class PostFeedResponse(BaseModel):
    """Envelope used when returning a collection of posts."""

    items: list[PostResponse]


class PostEngagementResponse(BaseModel):
    """Like/comment counters used by interactive UI."""

    post_id: UUID
    like_count: int
    dislike_count: int
    comment_count: int
    viewer_has_liked: bool
    viewer_has_disliked: bool


class PostCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)
    parent_id: UUID | None = None


class PostCommentUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)


class PostCommentResponse(BaseModel):
    id: UUID
    post_id: UUID
    user_id: UUID
    username: str | None = None
    avatar_url: str | None = None
    role: str | None = None
    content: str
    parent_id: UUID | None = None
    created_at: datetime
    replies: list["PostCommentResponse"] = Field(default_factory=list)


class PostCommentListResponse(BaseModel):
    items: list[PostCommentResponse]


PostCommentResponse.model_rebuild()


__all__ = [
    "PostCreate",
    "PostResponse",
    "PostFeedResponse",
    "PostEngagementResponse",
    "PostCommentCreate",
    "PostCommentUpdate",
    "PostCommentResponse",
    "PostCommentListResponse",
]
