"""Domain model for group chat metadata."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from uuid import uuid4

from .base import utc_now


@dataclass
class GroupChatRecord:
    name: str
    owner: str
    members: List[str]
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


__all__ = ["GroupChatRecord"]
