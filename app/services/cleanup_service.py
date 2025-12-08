"""Automated cleanup utilities for pruning expired social data."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import MediaAsset, Message, Notification, Post, Story
from .media_service import media_url_is_fetchable

logger = logging.getLogger(__name__)

DEFAULT_RETENTION: timedelta = timedelta(days=2)


class CleanupError(RuntimeError):
    """Raised when the cleanup task cannot complete successfully."""


@dataclass(frozen=True, slots=True)
class CleanupSummary:
    """Represents the number of records deleted during a cleanup run."""

    posts: int
    stories: int
    direct_messages: int
    group_messages: int
    notifications: int
    broken_post_media: int = 0

    @property
    def total(self) -> int:
        """Return the total number of deleted rows."""

        return self.posts + self.stories + self.direct_messages + self.group_messages + self.notifications


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
        Counts describing how many rows were removed per table and how many
        posts had stale media references detached.

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
    delete_stories = delete(Story).where(Story.expires_at < datetime.now(timezone.utc)).returning(Story.id)

    try:
        detached_media_posts = _detach_broken_post_media(session)
        posts_deleted = _execute_delete(session, delete_posts)
        stories_deleted = _execute_delete(session, delete_stories)
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
        stories=stories_deleted,
        direct_messages=direct_deleted,
        group_messages=group_deleted,
        notifications=notifications_deleted,
        broken_post_media=detached_media_posts,
    )

    logger.info(
        "Cleanup finished (posts=%d, stories=%d, direct_messages=%d, group_messages=%d, notifications=%d, total=%d)",
        summary.posts,
        summary.stories,
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


def _detach_broken_post_media(session: Session) -> int:
    """Remove media references from posts whose files no longer exist."""

    stmt = (
        select(Post.id, Post.media_url, Post.media_asset_id, MediaAsset.url.label("asset_url"))
        .outerjoin(MediaAsset, MediaAsset.id == Post.media_asset_id)
        .where(or_(Post.media_asset_id.is_not(None), Post.media_url.is_not(None)))
        .execution_options(yield_per=64)
    )

    broken_post_ids: list[UUID] = []
    for post_id, post_media_url, _media_asset_id, asset_url in session.execute(stmt):
        candidate_url = (post_media_url or asset_url or "").strip()
        if not candidate_url or not media_url_is_fetchable(candidate_url):
            broken_post_ids.append(post_id)

    if not broken_post_ids:
        return 0

    unique_post_ids = list({post_id for post_id in broken_post_ids})
    posts = session.query(Post).filter(Post.id.in_(unique_post_ids)).all()
    detached = 0
    for post in posts:
        if post.media_asset_id is not None or post.media_url:
            post.media_asset_id = None
            post.media_url = None
            detached += 1

    if detached:
        logger.info("Detached media from %d posts referencing missing files", detached)

    return detached


__all__ = [
    "CleanupError",
    "CleanupSummary",
    "DEFAULT_RETENTION",
    "perform_cleanup",
    "run_cleanup",
]
