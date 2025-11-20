"""Domain model for user accounts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .base import utc_now


@dataclass
class UserRecord:
    username: str
    password_hash: str
    email: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)
    last_active_at: datetime = field(default_factory=utc_now)


__all__ = ["UserRecord"]
