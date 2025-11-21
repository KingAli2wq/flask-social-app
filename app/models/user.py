"""Domain model for user accounts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from .base import utc_now


@dataclass
class UserRecord:
    username: str
    password_hash: str
    id: UUID = field(default_factory=uuid4)
    email: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    last_active_at: datetime = field(default_factory=utc_now)


__all__ = ["UserRecord"]
