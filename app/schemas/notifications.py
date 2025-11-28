"""Schemas for notifications."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    recipient_id: UUID
    sender_id: UUID
    type: str
    content: str
    created_at: datetime
    read: bool
    payload: dict[str, Any] | None = None
    emailed_at: datetime | None = None


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]


class NotificationSummaryResponse(BaseModel):
    unread_count: int = 0


__all__ = ["NotificationResponse", "NotificationListResponse", "NotificationSummaryResponse"]
