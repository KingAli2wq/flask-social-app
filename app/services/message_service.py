"""Messaging domain services backed by PostgreSQL."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import GroupChat, Message, User
from ..schemas import GroupChatCreate, MessageSendRequest


def create_group_chat(db: Session, owner: User, payload: GroupChatCreate) -> GroupChat:
    """Create a persisted group chat and attach the requested members."""

    candidate_usernames: list[str] = []
    for raw in [owner.username, *payload.members]:
        username = raw.strip()
        if not username:
            continue
        if username not in candidate_usernames:
            candidate_usernames.append(username)

    members: list[User] = []
    for username in candidate_usernames:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{username}' not found")
        members.append(user)

    chat = GroupChat(name=payload.name, owner_id=owner.id)
    chat.members = members

    try:
        db.add(chat)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create group chat") from exc

    db.refresh(chat)
    return chat


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
) -> Message:
    """Persist a message to PostgreSQL."""

    if not payload.chat_id and payload.recipient_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="chat_id or recipient_id required")

    group_chat_id: UUID | None = None
    chat_identifier = payload.chat_id

    if payload.chat_id:
        try:
            group_chat_uuid = UUID(payload.chat_id)
        except ValueError:
            group_chat_uuid = None

        if group_chat_uuid is not None:
            chat = db.get(GroupChat, group_chat_uuid)
            if chat is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group chat not found")
            group_chat_id = chat.id
            chat_identifier = str(chat.id)

    recipient_id: UUID | None = payload.recipient_id
    if recipient_id is not None and db.get(User, recipient_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")

    message = Message(
        chat_id=chat_identifier,
        group_chat_id=group_chat_id,
        sender_id=sender.id,
        recipient_id=recipient_id,
        content=payload.content,
        attachments=_attachments_or_none(payload.attachments),
    )

    try:
        db.add(message)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to persist message") from exc

    db.refresh(message)

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
