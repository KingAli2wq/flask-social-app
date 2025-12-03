"""Schemas describing moderation dashboards."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ModerationStats(BaseModel):
    total_users: int
    active_last_24h: int
    total_posts: int
    total_media_assets: int


class ModerationUserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str | None = None
    email: str | None = None
    role: str | None = None
    post_count: int = 0
    created_at: datetime
    last_active_at: datetime | None = None
    email_verified: bool = False


class ModerationPostSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    caption: str
    created_at: datetime
    user_id: UUID
    username: str
    display_name: str | None = None
    role: str | None = None
    media_asset_id: UUID | None = None
    media_url: str | None = None
    like_count: int = 0
    dislike_count: int = 0
    comment_count: int = 0


class ModerationDashboardResponse(BaseModel):
    stats: ModerationStats
    recent_users: list[ModerationUserSummary]
    recent_posts: list[ModerationPostSummary]


class ModerationRoleUpdateRequest(BaseModel):
    role: Literal["owner", "admin", "user"]


__all__ = [
    "ModerationStats",
    "ModerationUserSummary",
    "ModerationPostSummary",
    "ModerationDashboardResponse",
    "ModerationRoleUpdateRequest",
]
