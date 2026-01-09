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
    avatar_url: str | None = None
    post_count: int = 0
    media_count: int = 0
    created_at: datetime
    last_active_at: datetime | None = None
    email_verified: bool = False
    banned_at: datetime | None = None
    banned_until: datetime | None = None
    ban_reason: str | None = None
    is_banned: bool = False


class ModerationUserList(BaseModel):
    total: int
    items: list[ModerationUserSummary]


class ModerationUserDetail(ModerationUserSummary):
    bio: str | None = None
    location: str | None = None
    website: str | None = None
    follower_count: int = 0
    following_count: int = 0
    allow_friend_requests: bool | None = None
    dm_followers_only: bool | None = None


class ModerationUserBanRequest(BaseModel):
    unit: Literal["minutes", "hours", "days", "months", "years", "permanent"]
    value: int | None = None
    reason: str | None = None


class ModerationUserUpdateRequest(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    location: str | None = None
    website: str | None = None
    avatar_url: str | None = None
    email: str | None = None
    allow_friend_requests: bool | None = None
    dm_followers_only: bool | None = None


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


class ModerationPostList(BaseModel):
    total: int
    items: list[ModerationPostSummary]


class ModerationPostDetail(ModerationPostSummary):
    avatar_url: str | None = None


class ModerationPostUpdateRequest(BaseModel):
    caption: str | None = None
    remove_media: bool | None = None
    media_asset_id: UUID | None = None


class ModerationDashboardResponse(BaseModel):
    stats: ModerationStats
    recent_users: list[ModerationUserSummary]
    recent_posts: list[ModerationPostSummary]


class ModerationRoleUpdateRequest(BaseModel):
    role: Literal["owner", "admin", "user"]


class ModerationMediaSummary(BaseModel):
    id: UUID
    user_id: UUID | None = None
    username: str | None = None
    display_name: str | None = None
    role: str | None = None
    avatar_url: str | None = None
    url: str
    key: str | None = None
    bucket: str | None = None
    folder: str | None = None
    content_type: str | None = None
    created_at: datetime
    like_count: int = 0
    dislike_count: int = 0
    comment_count: int = 0


class ModerationMediaList(BaseModel):
    total: int
    items: list[ModerationMediaSummary]


class ModerationMediaDetail(ModerationMediaSummary):
    pass


__all__ = [
    "ModerationStats",
    "ModerationUserSummary",
    "ModerationUserList",
    "ModerationUserDetail",
    "ModerationUserUpdateRequest",
    "ModerationUserBanRequest",
    "ModerationPostSummary",
    "ModerationPostList",
    "ModerationPostDetail",
    "ModerationPostUpdateRequest",
    "ModerationDashboardResponse",
    "ModerationRoleUpdateRequest",
    "ModerationMediaSummary",
    "ModerationMediaList",
    "ModerationMediaDetail",
]
