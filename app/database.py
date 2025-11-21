"""Database layer utilities for both PostgreSQL and legacy in-memory storage."""
from __future__ import annotations

import logging
import os
from typing import Dict, Generator, List, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .models import (
    GroupChatRecord,
    MessageRecord,
    NotificationRecord,
    PostRecord,
    UserRecord,
)
from .models.base import utc_now

logger = logging.getLogger(__name__)

# Load environment variables so DATABASE_URL is available when the module is imported.
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

engine: Engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_engine() -> Engine:
    """Return the configured SQLAlchemy engine."""

    return engine


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy session per request."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_session() -> Session:
    """Return a new SQLAlchemy session for background tasks or scripts."""

    return SessionLocal()


def init_db() -> None:
    """Initialise database schema by creating tables when missing."""

    # Late import to avoid circular dependencies during startup.
    from .db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------------
# Legacy in-memory database (retained for backwards compatibility)
# ---------------------------------------------------------------------------


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
    "Base",
    "FakeDatabase",
    "GroupChatRecord",
    "MessageRecord",
    "NotificationRecord",
    "PostRecord",
    "UserRecord",
    "get_database",
    "get_engine",
    "get_session",
    "create_session",
    "init_db",
]
