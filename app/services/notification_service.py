"""Notification helper logic for PostgreSQL-backed storage."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Notification, User
from ..schemas import NotificationResponse
from .email_service import EmailDeliveryError, send_email
from .notification_stream import notification_stream_manager

logger = logging.getLogger(__name__)


class NotificationType(StrEnum):
    GENERIC = "generic"
    MESSAGE_RECEIVED = "message.received"
    NEW_FOLLOWER = "follow.new"
    FRIEND_REQUEST = "friend.request"
    FRIEND_ADDED = "friend.added"
    POST_FROM_FOLLOWED = "post.followed_author"
    POST_COMMENT = "post.comment"
    POST_COMMENT_REPLY = "post.comment.reply"
    POST_LIKE = "post.like"


DEFAULT_NOTIFICATION_TYPE = NotificationType.GENERIC


def list_notifications(db: Session, user_id: UUID) -> list[Notification]:
    """Return notifications for the supplied recipient ordered newest first."""

    stmt = select(Notification).where(Notification.recipient_id == user_id).order_by(Notification.created_at.desc())
    return list(db.scalars(stmt))


def count_unread_notifications(db: Session, user_id: UUID) -> int:
    """Return the unread notification total for the supplied user."""

    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.recipient_id == user_id, Notification.read.is_(False))
    )
    return int(db.scalar(stmt) or 0)


def add_notification(
    db: Session,
    *,
    recipient_id: UUID,
    content: str,
    sender_id: UUID,
    type_: NotificationType | str = DEFAULT_NOTIFICATION_TYPE,
    payload: dict[str, Any] | None = None,
    send_email_notification: bool = False,
    email_subject: str | None = None,
    email_body: str | None = None,
) -> Notification:
    """Persist a new notification for the given recipient."""

    recipient = db.get(User, recipient_id)
    if recipient is None:
        raise ValueError("Recipient does not exist")

    sender = db.get(User, sender_id)
    if sender is None:
        raise ValueError("Sender does not exist")

    notification = Notification(
        recipient_id=recipient_id,
        sender_id=sender_id,
        type=str(type_),
        content=content,
        payload=payload,
        created_at=datetime.now(timezone.utc),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    if send_email_notification:
        _maybe_send_notification_email(db, notification, recipient, email_subject, email_body)

    _broadcast_notification(notification)
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
    _schedule_notification_event(recipient_id, {"type": "notification.read_all"})


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


def _maybe_send_notification_email(
    db: Session,
    notification: Notification,
    recipient: User,
    email_subject: str | None,
    email_body: str | None,
) -> None:
    if not recipient.email:
        return

    subject = email_subject or "You have a new notification"
    body = email_body or _default_email_body(notification)
    try:
        delivered = send_email(recipient.email, subject, body)
    except EmailDeliveryError:
        logger.warning("Email delivery failed for notification %s", notification.id)
        return

    if not delivered:
        return

    setattr(notification, "emailed_at", datetime.now(timezone.utc))
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()


def _default_email_body(notification: Notification) -> str:
    settings = get_settings()
    base_url = settings.public_base_url.rstrip("/")
    return (
        f"{notification.content}\n\n"
        f"View more on SocialSphere: {base_url}/notifications"
    )


def _broadcast_notification(notification: Notification) -> None:
    payload = {
        "type": "notification.created",
        "notification": NotificationResponse.model_validate(notification).model_dump(),
    }
    _schedule_notification_event(notification.recipient_id, payload)


def _schedule_notification_event(user_id: UUID | str, payload: dict[str, Any]) -> None:
    target = str(user_id)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(notification_stream_manager.broadcast([target], payload))


__all__ = [
    "NotificationType",
    "list_notifications",
    "count_unread_notifications",
    "add_notification",
    "mark_all_read",
    "delete_old_notifications",
]
