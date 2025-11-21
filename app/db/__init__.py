"""Backwards-compatible shims for ORM models.

This package previously housed the canonical SQLAlchemy models. The models have
been moved to :mod:`app.models`; the imports below exist to preserve older
import paths.
"""

from app.models import MediaAsset, Message, Notification, Post, User

__all__ = ["User", "Post", "Message", "Notification", "MediaAsset"]
