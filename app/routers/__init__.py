"""Aggregate router exports."""
from .auth import router as auth_router
from .messages import router as messages_router
from .notifications import router as notifications_router
from .posts import router as posts_router
from .profiles import router as profiles_router
from .uploads import router as uploads_router

__all__ = [
    "auth_router",
    "messages_router",
    "notifications_router",
    "posts_router",
    "profiles_router",
    "uploads_router",
]
