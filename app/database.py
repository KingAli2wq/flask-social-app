"""Application data access layer.

This module exposes a very small in-memory data store that simulates the
behaviour of a database. The functions mirror CRUD style interactions so that
they can be swapped with a real database implementation (for example,
SQLAlchemy + PostgreSQL) at a later time without touching the routers.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .models import (
    GroupChatRecord,
    MessageRecord,
    NotificationRecord,
    PostRecord,
    UserRecord,
)
from .models.base import utc_now


class FakeDatabase:
    """Minimal in-memory data store with CRUD style helpers."""

    def __init__(self) -> None:
        self._users: Dict[str, UserRecord] = {}
        self._posts: Dict[str, PostRecord] = {}
        self._messages: Dict[str, List[MessageRecord]] = {}
        self._group_chats: Dict[str, GroupChatRecord] = {}
        self._notifications: Dict[str, List[NotificationRecord]] = {}

    # --- user operations -------------------------------------------------
    def create_user(self, record: UserRecord) -> UserRecord:
        self._users[record.username] = record
        return record

    def get_user(self, username: str) -> Optional[UserRecord]:
        return self._users.get(username)

    def list_users(self) -> List[UserRecord]:
        return list(self._users.values())

    def update_user(self, username: str, **fields: object) -> Optional[UserRecord]:
        user = self._users.get(username)
        if not user:
            return None
        for key, value in fields.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)
        user.last_active_at = utc_now()
        return user

    # --- post operations -------------------------------------------------
    def create_post(self, record: PostRecord) -> PostRecord:
        self._posts[record.id] = record
        return record

    def get_post(self, post_id: str) -> Optional[PostRecord]:
        return self._posts.get(post_id)

    def list_posts(self) -> List[PostRecord]:
        return list(self._posts.values())

    def delete_post(self, post_id: str) -> bool:
        return self._posts.pop(post_id, None) is not None

    # --- message operations ---------------------------------------------
    def create_message(self, record: MessageRecord) -> MessageRecord:
        thread = self._messages.setdefault(record.chat_id, [])
        thread.append(record)
        return record

    def list_messages(self, chat_id: str) -> List[MessageRecord]:
        return list(self._messages.get(chat_id, []))

    # --- group chat operations ------------------------------------------
    def create_group_chat(self, record: GroupChatRecord) -> GroupChatRecord:
        self._group_chats[record.id] = record
        return record

    def get_group_chat(self, chat_id: str) -> Optional[GroupChatRecord]:
        return self._group_chats.get(chat_id)

    def list_group_chats_for_user(self, username: str) -> List[GroupChatRecord]:
        return [chat for chat in self._group_chats.values() if username in chat.members]

    # --- notification operations ----------------------------------------
    def add_notification(self, record: NotificationRecord) -> NotificationRecord:
        bucket = self._notifications.setdefault(record.recipient, [])
        bucket.append(record)
        return record

    def list_notifications(self, recipient: str) -> List[NotificationRecord]:
        return list(self._notifications.get(recipient, []))

    def mark_notifications_read(self, recipient: str) -> None:
        for note in self._notifications.get(recipient, []):
            note.read = True


_db = FakeDatabase()


def get_database() -> FakeDatabase:
    """FastAPI dependency hook returning the singleton database instance."""
    return _db


__all__ = [
    "FakeDatabase",
    "UserRecord",
    "PostRecord",
    "MessageRecord",
    "NotificationRecord",
    "GroupChatRecord",
    "get_database",
]
