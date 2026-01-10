"""Schemas used by messaging endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MessageSendRequest(BaseModel):
    chat_id: str | None = Field(None, description="Unique identifier for a group chat thread")
    friend_id: UUID | None = Field(None, description="Direct message recipient derived from friendships")
    content: str = Field("", min_length=0, max_length=2000)
    attachments: List[str] = Field(default_factory=list)
    reply_to_id: UUID | None = Field(None, description="Optional message being replied to")

    @model_validator(mode="after")
    def ensure_payload(self) -> "MessageSendRequest":
        has_text = bool((self.content or "").strip())
        has_attachments = any(bool(item) for item in self.attachments)
        if not (has_text or has_attachments):
            raise ValueError("Message must include text or at least one attachment")
        return self


class MessageReplyContext(BaseModel):
    id: UUID
    sender_id: UUID
    sender_username: str | None = None
    sender_display_name: str | None = None
    sender_avatar_url: str | None = None
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
    sender_display_name: str | None = None
    sender_avatar_url: str | None = None
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
    avatar_url: str | None = Field(default=None, max_length=512)


class GroupChatInviteRequest(BaseModel):
    members: List[str] = Field(..., min_length=1, description="Usernames to invite into the chat")

    @model_validator(mode="after")
    def ensure_members(self) -> "GroupChatInviteRequest":
        cleaned = [member.strip() for member in self.members if member and member.strip()]
        if not cleaned:
            raise ValueError("At least one username is required")
        self.members = cleaned
        return self


class GroupChatUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=60)
    avatar_url: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def ensure_changes(self) -> "GroupChatUpdateRequest":
        cleaned_name = (self.name or "").strip()
        cleaned_avatar = (self.avatar_url or "").strip()
        if not cleaned_name and not cleaned_avatar:
            raise ValueError("Provide at least one field to update")
        if cleaned_name and len(cleaned_name) < 3:
            raise ValueError("Group name must be at least 3 characters long")
        self.name = cleaned_name or None
        self.avatar_url = cleaned_avatar or None
        return self


class GroupChatMemberRemoveRequest(BaseModel):
    members: List[str] = Field(..., min_length=1, description="Usernames to remove from the chat")

    @model_validator(mode="after")
    def ensure_members(self) -> "GroupChatMemberRemoveRequest":
        cleaned = [member.strip() for member in self.members if member and member.strip()]
        if not cleaned:
            raise ValueError("At least one username is required")
        self.members = cleaned
        return self


class GroupChatResponse(BaseModel):
    id: UUID
    name: str
    owner: str
    owner_id: UUID | None = None
    members: List[str]
    member_roles: Dict[str, str] = Field(default_factory=dict)
    avatar_url: str | None = None
    lock_code: str
    created_at: datetime
    updated_at: datetime


class GroupChatMemberRoleUpdateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=60)
    role: Literal["member", "moderator", "admin", "leader"]


__all__ = [
    "MessageSendRequest",
    "MessageReplyContext",
    "MessageResponse",
    "MessageThreadResponse",
    "DirectThreadResponse",
    "GroupChatCreate",
    "GroupChatResponse",
    "GroupChatInviteRequest",
    "GroupChatUpdateRequest",
    "GroupChatMemberRemoveRequest",
    "GroupChatMemberRoleUpdateRequest",
]
