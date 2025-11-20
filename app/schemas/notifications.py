"""Schemas for notifications."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    body: str
    created_at: datetime
    read: bool


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]


__all__ = ["NotificationResponse", "NotificationListResponse"]
