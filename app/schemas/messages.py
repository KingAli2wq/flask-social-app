"""Schemas used by messaging endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MessageSendRequest(BaseModel):
    chat_id: str | None = Field(None, description="Unique identifier for a group chat thread")
    friend_id: UUID | None = Field(None, description="Direct message recipient derived from friendships")
    content: str = Field(..., min_length=1, max_length=2000)
    attachments: List[str] = Field(default_factory=list)
    reply_to_id: UUID | None = Field(None, description="Optional message being replied to")


class MessageReplyContext(BaseModel):
    id: UUID
    sender_id: UUID
    sender_username: str | None = None
    content: str | None = None
    is_deleted: bool = False


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chat_id: str | None
    sender_id: UUID
    recipient_id: UUID | None
    content: str
    attachments: List[str]
    created_at: datetime
    sender_username: str | None = None
    reply_to: MessageReplyContext | None = None
    is_deleted: bool = False
    deleted_at: datetime | None = None


class MessageThreadResponse(BaseModel):
    chat_id: str | None
    messages: List[MessageResponse]


class DirectThreadResponse(BaseModel):
    chat_id: str | None
    friend_id: UUID
    friend_username: str
    friend_avatar_url: str | None
    lock_code: str
    messages: List[MessageResponse]


class GroupChatCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=60)
    members: List[str] = Field(default_factory=list)


class GroupChatResponse(BaseModel):
    id: UUID
    name: str
    owner: str
    members: List[str]
    created_at: datetime
    updated_at: datetime


__all__ = [
    "MessageSendRequest",
    "MessageReplyContext",
    "MessageResponse",
    "MessageThreadResponse",
    "DirectThreadResponse",
    "GroupChatCreate",
    "GroupChatResponse",
]
