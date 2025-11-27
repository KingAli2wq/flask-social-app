"""Schemas supporting follower APIs."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class FollowStatsResponse(BaseModel):
    user_id: UUID
    followers_count: int
    following_count: int
    is_following: bool


class FollowActionResponse(FollowStatsResponse):
    status: Literal["followed", "unfollowed", "noop"]


__all__ = ["FollowStatsResponse", "FollowActionResponse"]
