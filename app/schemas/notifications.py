"""Schemas for notifications."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: UUID
    recipient_id: UUID
    actor_id: UUID | None
    type: str
    content: str
    created_at: datetime
    read: bool


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]


__all__ = ["NotificationResponse", "NotificationListResponse"]
