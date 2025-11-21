"""Messaging domain services backed by PostgreSQL."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import FakeDatabase
from ..db import Message, User
from ..models import GroupChatRecord, MessageRecord, UserRecord
from ..schemas import GroupChatCreate, MessageSendRequest


def create_group_chat(db: FakeDatabase, owner: User | UserRecord, payload: GroupChatCreate) -> GroupChatRecord:
    """Maintain legacy group chat support via the in-memory store."""

    members = list(dict.fromkeys([owner.username, *payload.members]))
    record = GroupChatRecord(name=payload.name, owner=owner.username, members=members)
    db.create_group_chat(record)
    return record


def _attachments_or_none(values: Iterable[str] | None) -> list[str] | None:
    if not values:
        return None
    cleaned = [value for value in values if value]
    return cleaned or None


def send_message(
    db: Session,
    *,
    sender: User,
    payload: MessageSendRequest,
    legacy_store: FakeDatabase | None = None,
) -> Message:
    """Persist a message to PostgreSQL and mirror to the legacy store when provided."""

    if not payload.chat_id and payload.recipient_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="chat_id or recipient_id required")

    recipient_id: UUID | None = payload.recipient_id
    if recipient_id is not None and db.get(User, recipient_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")

    message = Message(
        chat_id=payload.chat_id,
        sender_id=sender.id,
        recipient_id=recipient_id,
        content=payload.content,
        attachments=_attachments_or_none(payload.attachments),
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    if legacy_store is not None:
        legacy_record = MessageRecord(
            chat_id=payload.chat_id or str(recipient_id or ""),
            sender=sender.username,
            content=payload.content,
            attachments=payload.attachments,
        )
        legacy_store.create_message(legacy_record)

    return message


def list_messages(db: Session, *, chat_id: str) -> list[Message]:
    """Return messages for the provided chat ordered chronologically."""

    stmt = select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.asc())
    return list(db.scalars(stmt))


def delete_old_messages(db: Session, *, older_than: timedelta | None = None) -> int:
    """Delete chat messages older than the provided delta (default 2 days)."""

    cutoff = datetime.now(timezone.utc) - (older_than or timedelta(days=2))
    stmt = delete(Message).where(Message.created_at < cutoff).returning(Message.id)
    try:
        result = db.execute(stmt)
        deleted = result.fetchall()
        db.commit()
        return len(deleted)
    except SQLAlchemyError:
        db.rollback()
        return 0


__all__ = [
    "create_group_chat",
    "send_message",
    "list_messages",
    "delete_old_messages",
]
