"""Export page routers for composition."""
from __future__ import annotations

from . import auth, friends, home, media, messages, notifications, profile

__all__ = [
    "auth",
    "friends",
    "home",
    "media",
    "messages",
    "notifications",
    "profile",
]
