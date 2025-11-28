"""Messaging domain services backed by PostgreSQL."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from ..models import GroupChat, Message, User
from ..schemas import GroupChatCreate, MessageSendRequest
from .friendship_service import require_friendship
from .notification_service import NotificationType, add_notification


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

    if not payload.chat_id and payload.friend_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="friend_id or chat_id required")

    group_chat_id: UUID | None = None
    chat_identifier = payload.chat_id

    recipient_id: UUID | None = None
    parent_message: Message | None = None

    if payload.friend_id is not None:
        friendship, friend = require_friendship(db, user=sender, friend_id=payload.friend_id)
        chat_identifier = friendship.thread_id
        recipient_id = cast(UUID, friend.id)
    elif payload.chat_id:
        try:
            group_chat_uuid = UUID(payload.chat_id)
        except ValueError:
            group_chat_uuid = None

        if group_chat_uuid is not None:
            chat = db.get(GroupChat, group_chat_uuid)
            if chat is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group chat not found")
            group_chat_id = cast(UUID, chat.id)
            chat_identifier = str(chat.id)

    if recipient_id is None and payload.friend_id is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Friendship required")

    if payload.reply_to_id is not None:
        parent_message = db.get(Message, payload.reply_to_id)
        if parent_message is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply target not found")
        parent_chat_id = cast(str | None, parent_message.chat_id)
        if parent_chat_id != chat_identifier:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply must stay within the same chat")

    message = Message(
        chat_id=chat_identifier,
        group_chat_id=group_chat_id,
        sender_id=sender.id,
        recipient_id=recipient_id,
        content=payload.content,
        attachments=_attachments_or_none(payload.attachments),
        parent_id=parent_message.id if parent_message else None,
    )

    try:
        db.add(message)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to persist message") from exc

    db.refresh(message)

    if recipient_id is not None:
        _notify_direct_message(db, sender=sender, recipient_id=recipient_id, message=message)

    return message


def list_messages(db: Session, *, chat_id: str) -> list[Message]:
    """Return messages for the provided chat ordered chronologically."""

    stmt = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .options(
            selectinload(Message.sender),
            selectinload(Message.parent).selectinload(Message.sender),
        )
        .order_by(Message.created_at.asc())
    )
    return list(db.scalars(stmt))


def delete_message(db: Session, *, message_id: UUID, requester: User) -> Message:
    message = db.get(Message, message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    sender_id = cast(UUID, message.sender_id)
    if sender_id != requester.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own messages")
    if cast(bool, message.is_deleted):
        return message

    setattr(message, "is_deleted", True)
    setattr(message, "deleted_at", datetime.now(timezone.utc))
    setattr(message, "content", "")
    setattr(message, "attachments", None)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete message") from exc

    db.refresh(message)
    return message


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
    "delete_message",
    "delete_old_messages",
]


def _notify_direct_message(db: Session, *, sender: User, recipient_id: UUID, message: Message) -> None:
    if recipient_id == sender.id:
        return
    preview = (message.content or "").strip()
    sender_id = cast(UUID, sender.id)
    chat_identifier = cast(str | None, message.chat_id)
    payload = {
        "message_id": str(message.id),
        "chat_id": chat_identifier,
        "preview": preview[:160],
    }
    add_notification(
        db,
        recipient_id=recipient_id,
        sender_id=sender_id,
        content=f"@{sender.username or 'A user'} sent you a new message.",
        type_=NotificationType.MESSAGE_RECEIVED,
        payload=payload,
        send_email_notification=True,
    )
