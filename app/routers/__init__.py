"""Aggregate router exports."""
from .auth import router as auth_router
from .chatbot import router as chatbot_router
from .friends import router as friends_router
from .follows import router as follows_router
from .media import router as media_router
from .messages import router as messages_router
from .notifications import router as notifications_router
from .moderation import router as moderation_router
from .posts import router as posts_router
from .profiles import router as profiles_router
from .realtime import router as realtime_router
from .settings import router as settings_router
from .stories import router as stories_router
from .uploads import router as uploads_router

__all__ = [
    "auth_router",
    "chatbot_router",
    "friends_router",
    "follows_router",
    "media_router",
    "messages_router",
    "notifications_router",
    "moderation_router",
    "posts_router",
    "profiles_router",
    "realtime_router",
    "settings_router",
    "stories_router",
    "uploads_router",
]
