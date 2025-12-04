"""Schemas for media uploads and immersive feed interactions."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MediaUploadResponse(BaseModel):
    """Response returned after uploading a file to Spaces."""

    id: UUID = Field(..., description="Unique identifier for the persisted media asset")
    url: str = Field(..., description="Public URL of the uploaded asset")
    key: str = Field(..., description="Object key inside the Spaces bucket")
    bucket: str = Field(..., description="Target DigitalOcean Spaces bucket")
    content_type: str = Field(..., description="MIME type associated with the uploaded file")


class MediaFeedItem(BaseModel):
    """Single media asset returned inside the vertical reel."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None = None
    username: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    role: str | None = None
    url: str
    content_type: str
    created_at: datetime
    like_count: int = 0
    dislike_count: int = 0
    comment_count: int = 0
    viewer_has_liked: bool = False
    viewer_has_disliked: bool = False


class MediaFeedResponse(BaseModel):
    items: list[MediaFeedItem]


class MediaEngagementResponse(BaseModel):
    media_asset_id: UUID
    like_count: int
    dislike_count: int
    comment_count: int
    viewer_has_liked: bool
    viewer_has_disliked: bool


class MediaCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)
    parent_id: UUID | None = None


class MediaCommentResponse(BaseModel):
    id: UUID
    media_asset_id: UUID
    user_id: UUID
    username: str | None = None
    avatar_url: str | None = None
    role: str | None = None
    content: str
    parent_id: UUID | None = None
    created_at: datetime
    replies: list["MediaCommentResponse"] = Field(default_factory=list)


class MediaCommentListResponse(BaseModel):
    items: list[MediaCommentResponse]


class MediaVerificationResponse(BaseModel):
    media_asset_id: UUID
    deleted: bool = False
    missing: bool = False


MediaCommentResponse.model_rebuild()


__all__ = [
    "MediaUploadResponse",
    "MediaFeedItem",
    "MediaFeedResponse",
    "MediaEngagementResponse",
    "MediaCommentCreate",
    "MediaCommentResponse",
    "MediaCommentListResponse",
    "MediaVerificationResponse",
]
