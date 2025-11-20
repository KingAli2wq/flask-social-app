"""Schemas used by messaging endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class MessageSendRequest(BaseModel):
    chat_id: str = Field(..., description="Unique identifier for the chat thread")
    content: str = Field(..., min_length=1, max_length=2000)
    attachments: List[str] = Field(default_factory=list)


class MessageResponse(BaseModel):
    id: str
    chat_id: str
    sender: str
    content: str
    attachments: List[str]
    created_at: datetime


class MessageThreadResponse(BaseModel):
    chat_id: str
    messages: List[MessageResponse]


class GroupChatCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=60)
    members: List[str] = Field(default_factory=list)


class GroupChatResponse(BaseModel):
    id: str
    name: str
    owner: str
    members: List[str]
    created_at: datetime
    updated_at: datetime


__all__ = [
    "MessageSendRequest",
    "MessageResponse",
    "MessageThreadResponse",
    "GroupChatCreate",
    "GroupChatResponse",
]
