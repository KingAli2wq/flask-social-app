"""Domain model for chat messages."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from uuid import uuid4

from .base import utc_now


@dataclass
class MessageRecord:
    chat_id: str
    sender: str
    content: str
    attachments: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)


__all__ = ["MessageRecord"]
