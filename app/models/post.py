"""Domain model for posts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Set
from uuid import uuid4

from .base import utc_now


@dataclass
class PostRecord:
    author: str
    content: str
    attachments: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime | None = None
    likes: Set[str] = field(default_factory=set)
    dislikes: Set[str] = field(default_factory=set)


__all__ = ["PostRecord"]
