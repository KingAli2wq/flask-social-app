"""Schemas for friend requests and directory listings."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FriendSummary(BaseModel):
    id: UUID = Field(..., description="Friend user ID")
    username: str
    avatar_url: str | None = None
    chat_id: str
    lock_code: str


class FriendRequestPayload(BaseModel):
    username: str = Field(..., min_length=3, max_length=150)


class FriendRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sender_id: UUID
    recipient_id: UUID
    status: str
    created_at: datetime


class FriendsOverviewResponse(BaseModel):
    friends: list[FriendSummary]
    incoming_requests: list[FriendRequestResponse]
    outgoing_requests: list[FriendRequestResponse]


__all__ = [
    "FriendSummary",
    "FriendRequestPayload",
    "FriendRequestResponse",
    "FriendsOverviewResponse",
]
