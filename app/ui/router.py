"""Aggregate UI page routes into a single router."""
from __future__ import annotations

from fastapi import APIRouter

from . import i18n
from .pages import auth, friends, home, media, messages, moderation, notifications, policy, profile, settings

router = APIRouter(include_in_schema=False)

router.include_router(i18n.router)
router.include_router(home.router)
router.include_router(auth.router)
router.include_router(friends.router)
router.include_router(profile.router)
router.include_router(messages.router)
router.include_router(notifications.router)
router.include_router(media.router)
router.include_router(settings.router)
router.include_router(moderation.router)
router.include_router(policy.router)

__all__ = ["router"]
