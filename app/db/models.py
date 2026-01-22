"""Backwards-compatible exports for ORM models.

Historically the database models lived in this module. To avoid duplicate table
registrations, we simply re-export the canonical models from :mod:`app.models`.
"""

from app.models import MediaAsset, Message, Notification, Post, Report, User

__all__ = ["User", "Post", "Message", "Notification", "MediaAsset", "Report"]
