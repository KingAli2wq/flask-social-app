"""Automated cleanup utilities for pruning expired social data."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..db import Message, Notification, Post

logger = logging.getLogger(__name__)

DEFAULT_RETENTION: timedelta = timedelta(days=2)


class CleanupError(RuntimeError):
    """Raised when the cleanup task cannot complete successfully."""


@dataclass(frozen=True, slots=True)
class CleanupSummary:
    """Represents the number of records deleted during a cleanup run."""

    posts: int
    direct_messages: int
    group_messages: int
    notifications: int

    @property
    def total(self) -> int:
        """Return the total number of deleted rows."""

        return self.posts + self.direct_messages + self.group_messages + self.notifications


def perform_cleanup(session: Session, *, retention: timedelta = DEFAULT_RETENTION) -> CleanupSummary:
    """Delete aged records from the database using the provided session.

    Parameters
    ----------
    session:
        An active SQLAlchemy :class:`Session` bound to the application's database.
    retention:
        A :class:`timedelta` defining how far back data should be retained. Defaults
        to two days.

    Returns
    -------
    CleanupSummary
        Counts describing how many rows were removed per table.

    Raises
    ------
    CleanupError
        If the cleanup process fails; the transaction is rolled back and the error
        is re-raised for callers to handle or log.
    """

    if retention <= timedelta(0):
        raise ValueError("retention must be a positive duration")

    cutoff = datetime.now(timezone.utc) - retention

    delete_posts = delete(Post).where(Post.created_at < cutoff).returning(Post.id)
    delete_direct_messages = delete(Message).where(
        Message.created_at < cutoff,
        Message.recipient_id.is_not(None),
    ).returning(Message.id)
    delete_group_messages = delete(Message).where(
        Message.created_at < cutoff,
        Message.chat_id.is_not(None),
    ).returning(Message.id)
    delete_notifications = delete(Notification).where(Notification.created_at < cutoff).returning(Notification.id)

    try:
        posts_deleted = _execute_delete(session, delete_posts)
        direct_deleted = _execute_delete(session, delete_direct_messages)
        group_deleted = _execute_delete(session, delete_group_messages)
        notifications_deleted = _execute_delete(session, delete_notifications)

        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        logger.exception("Cleanup failed; transaction rolled back")
        raise CleanupError("database cleanup failed") from exc

    summary = CleanupSummary(
        posts=posts_deleted,
        direct_messages=direct_deleted,
        group_messages=group_deleted,
        notifications=notifications_deleted,
    )

    logger.info(
        "Cleanup finished (posts=%d, direct_messages=%d, group_messages=%d, notifications=%d, total=%d)",
        summary.posts,
        summary.direct_messages,
        summary.group_messages,
        summary.notifications,
        summary.total,
    )

    return summary


def run_cleanup(session_factory: Callable[[], Session], *, retention: timedelta = DEFAULT_RETENTION) -> CleanupSummary:
    """Convenience helper to run cleanup using a session factory.

    This function is suitable for use inside a FastAPI startup event or scheduled
    background task where a new session should be scoped to the cleanup run.
    """

    session = session_factory()
    try:
        return perform_cleanup(session, retention=retention)
    finally:
        session.close()


def _execute_delete(session: Session, statement) -> int:
    """Execute a DELETE statement and return the number of affected rows."""

    result = session.execute(statement)
    deleted_ids = result.scalars().all()
    return len(deleted_ids)


__all__ = [
    "CleanupError",
    "CleanupSummary",
    "DEFAULT_RETENTION",
    "perform_cleanup",
    "run_cleanup",
]
