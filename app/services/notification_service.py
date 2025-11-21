"""Notification helper logic for PostgreSQL-backed storage."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..db import Notification, User

DEFAULT_NOTIFICATION_TYPE = "generic"


def list_notifications(db: Session, user_id: UUID) -> list[Notification]:
    """Return notifications for the supplied recipient ordered newest first."""

    stmt = select(Notification).where(Notification.recipient_id == user_id).order_by(Notification.created_at.desc())
    return list(db.scalars(stmt))


def add_notification(
    db: Session,
    *,
    recipient_id: UUID,
    content: str,
    actor_id: UUID | None = None,
    type_: str = DEFAULT_NOTIFICATION_TYPE,
) -> Notification:
    """Persist a new notification for the given recipient."""

    recipient = db.get(User, recipient_id)
    if recipient is None:
        raise ValueError("Recipient does not exist")

    if actor_id is not None and db.get(User, actor_id) is None:
        raise ValueError("Actor does not exist")

    notification = Notification(
        recipient_id=recipient_id,
        actor_id=actor_id,
        type=type_,
        content=content,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_read(db: Session, recipient_id: UUID) -> None:
    """Mark all notifications for the given recipient as read."""

    stmt = (
        update(Notification)
        .where(Notification.recipient_id == recipient_id, Notification.read.is_(False))
        .values(read=True)
    )
    db.execute(stmt)
    db.commit()


def delete_old_notifications(db: Session, *, older_than: timedelta | None = None) -> int:
    """Remove notifications older than the supplied delta (default 2 days)."""

    cutoff = datetime.now(timezone.utc) - (older_than or timedelta(days=2))
    stmt = delete(Notification).where(Notification.created_at < cutoff).returning(Notification.id)
    try:
        result = db.execute(stmt)
        rows = result.fetchall()
        db.commit()
        return len(rows)
    except SQLAlchemyError:
        db.rollback()
        return 0


__all__ = [
    "list_notifications",
    "add_notification",
    "mark_all_read",
    "delete_old_notifications",
]
