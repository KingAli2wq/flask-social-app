"""Notification helper logic."""
from __future__ import annotations

from ..database import FakeDatabase
from ..models import NotificationRecord


def list_notifications(db: FakeDatabase, username: str) -> list[NotificationRecord]:
    return db.list_notifications(username)


def add_notification(db: FakeDatabase, username: str, body: str) -> NotificationRecord:
    record = NotificationRecord(recipient=username, body=body)
    db.add_notification(record)
    return record


def mark_all_read(db: FakeDatabase, username: str) -> None:
    db.mark_notifications_read(username)


__all__ = ["list_notifications", "add_notification", "mark_all_read"]
