"""Domain model for notifications."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from .base import utc_now


@dataclass
class NotificationRecord:
    recipient: str
    body: str
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    read: bool = False


__all__ = ["NotificationRecord"]
