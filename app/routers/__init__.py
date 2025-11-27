"""Aggregate router exports."""
from .auth import router as auth_router
from .friends import router as friends_router
from .media import router as media_router
from .messages import router as messages_router
from .notifications import router as notifications_router
from .posts import router as posts_router
from .profiles import router as profiles_router
from .realtime import router as realtime_router
from .uploads import router as uploads_router

__all__ = [
    "auth_router",
    "friends_router",
    "media_router",
    "messages_router",
    "notifications_router",
    "posts_router",
    "profiles_router",
    "realtime_router",
    "uploads_router",
]
