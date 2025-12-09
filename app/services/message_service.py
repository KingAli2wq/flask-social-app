"""Messaging domain services backed by PostgreSQL."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Sequence, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from ..models import GroupChat, Message, User
from ..schemas import GroupChatCreate, MessageSendRequest
from ..security.data_vault import (
    DataVaultError,
    decrypt_text as vault_decrypt_text,
    encrypt_structured as vault_encrypt_structured,
    encrypt_text as vault_encrypt_text,
)
from .friendship_service import require_friendship
from .notification_service import NotificationType, add_notification
from .group_crypto import (
    GroupEncryptionError,
    encrypt_group_payload,
    generate_group_encryption_key,
    generate_group_lock_code,
)


def create_group_chat(db: Session, owner: User, payload: GroupChatCreate) -> GroupChat:
    """Create a persisted group chat and attach the requested members."""

    owner_username = cast(str | None, getattr(owner, "username", None))
    candidate_usernames = _collect_unique_usernames(owner_username, payload.members)
    members = _load_members_by_username(db, candidate_usernames)

    owner_id = _cast_uuid(cast(UUID | None, getattr(owner, "id", None)))

    chat = GroupChat(
        name=payload.name.strip(),
        owner_id=owner_id,
        avatar_url=(payload.avatar_url or None),
        encryption_key=generate_group_encryption_key(),
        lock_code=generate_group_lock_code(),
    )
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


def _encrypt_message_body(content: str, *, group_key: str | None) -> str:
    if group_key:
        return encrypt_group_payload(group_key, content)
    return vault_encrypt_text(content)


def _encrypt_message_attachments(
    attachments: list[str] | None,
    *,
    group_key: str | None,
) -> dict[str, Any] | list[str] | None:
    if not attachments:
        return None
    if group_key:
        blob = json.dumps(attachments, separators=(",", ":"))
        ciphertext = encrypt_group_payload(group_key, blob)
        return {
            "ciphertext": ciphertext,
            "encoding": "json",
            "scheme": "group.v1",
            "version": 1,
        }
    return vault_encrypt_structured(attachments)


def _collect_unique_usernames(owner_username: str | None, extras: Sequence[str] | None) -> list[str]:
    candidates: list[str] = []
    ordered_source: list[str] = [owner_username or ""]
    if extras:
        ordered_source.extend(extras)
    for raw in ordered_source:
        username = (raw or "").strip()
        if username and username not in candidates:
            candidates.append(username)
    return candidates


def _load_members_by_username(db: Session, usernames: Sequence[str]) -> list[User]:
    members: list[User] = []
    for username in usernames:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{username}' not found")
        members.append(user)
    return members


def send_message(
    db: Session,
    *,
    sender: User,
    payload: MessageSendRequest,
) -> Message:
    """Persist a message to PostgreSQL."""

    if not payload.chat_id and payload.friend_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="friend_id or chat_id required")

    attachments = _attachments_or_none(payload.attachments)
    has_text = bool((payload.content or "").strip())
    if not (has_text or attachments):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message requires text or attachments")

    group_chat_id: UUID | None = None
    chat_identifier = payload.chat_id
    target_group_chat: GroupChat | None = None
    group_encryption_key: str | None = None

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
            target_group_chat = db.get(GroupChat, group_chat_uuid)
            if target_group_chat is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group chat not found")
            _ensure_group_membership(target_group_chat, cast(UUID | None, getattr(sender, "id", None)))
            group_chat_id = cast(UUID, target_group_chat.id)
            chat_identifier = str(target_group_chat.id)

    if recipient_id is None and payload.friend_id is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Friendship required")

    if payload.reply_to_id is not None:
        parent_message = db.get(Message, payload.reply_to_id)
        if parent_message is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply target not found")
        parent_chat_id = cast(str | None, parent_message.chat_id)
        if parent_chat_id != chat_identifier:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply must stay within the same chat")

    message_content = payload.content or ""
    if target_group_chat is not None:
        try:
            group_encryption_key = cast(str | None, getattr(target_group_chat, "encryption_key", None))
        except AttributeError:  # pragma: no cover - defensive
            group_encryption_key = None
        if not group_encryption_key:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Group chat is missing an encryption key")
    plaintext_content = payload.content or ""
    try:
        message_content = _encrypt_message_body(plaintext_content, group_key=group_encryption_key)
    except (GroupEncryptionError, DataVaultError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to encrypt message") from exc

    try:
        encrypted_attachments = _encrypt_message_attachments(attachments, group_key=group_encryption_key)
    except (GroupEncryptionError, DataVaultError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to encrypt attachments") from exc

    message = Message(
        chat_id=chat_identifier,
        group_chat_id=group_chat_id,
        sender_id=sender.id,
        recipient_id=recipient_id,
        content=message_content,
        attachments=encrypted_attachments,
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
        _notify_direct_message(
            db,
            sender=sender,
            recipient_id=recipient_id,
            message=message,
            plaintext_preview=plaintext_content,
        )

    return message


def list_messages(db: Session, *, chat_id: str) -> list[Message]:
    """Return messages for the provided chat ordered chronologically."""

    stmt = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .options(
            selectinload(Message.sender),
            selectinload(Message.parent).selectinload(Message.sender),
            selectinload(Message.group_chat),
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


def list_group_chats(db: Session, *, user: User) -> list[GroupChat]:
    stmt = (
        select(GroupChat)
        .where(GroupChat.members.any(User.id == _cast_uuid(cast(UUID | None, getattr(user, "id", None)))))
        .options(selectinload(GroupChat.members), selectinload(GroupChat.owner))
        .order_by(GroupChat.updated_at.desc())
    )
    return list(db.scalars(stmt))


def get_group_chat(db: Session, *, chat_id: UUID, requester: User) -> GroupChat:
    stmt = (
        select(GroupChat)
        .where(
            GroupChat.id == chat_id,
            GroupChat.members.any(User.id == _cast_uuid(cast(UUID | None, getattr(requester, "id", None)))),
        )
        .options(selectinload(GroupChat.members), selectinload(GroupChat.owner))
    )
    chat = db.scalar(stmt)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group chat not found")
    return chat


def add_group_members(db: Session, *, chat_id: UUID, requester: User, usernames: Sequence[str]) -> GroupChat:
    normalized = [username.strip() for username in usernames if username and username.strip()]
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one username is required")

    chat = db.get(GroupChat, chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group chat not found")

    _ensure_group_membership(chat, cast(UUID | None, getattr(requester, "id", None)))
    _ensure_group_owner(chat, cast(UUID | None, getattr(requester, "id", None)))

    new_members = _load_members_by_username(db, normalized)
    existing_ids = {_cast_uuid(cast(UUID | None, getattr(member, "id", None))) for member in chat.members}
    added = False
    for user in new_members:
        user_id = _cast_uuid(cast(UUID | None, getattr(user, "id", None)))
        if user_id in existing_ids:
            continue
        chat.members.append(user)
        existing_ids.add(user_id)
        added = True

    if not added:
        return chat

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update group chat members") from exc

    db.refresh(chat)
    return chat


def update_group_chat(
    db: Session,
    *,
    chat_id: UUID,
    requester: User,
    name: str | None,
    avatar_url: str | None,
) -> GroupChat:
    chat = db.get(GroupChat, chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group chat not found")

    requester_id = cast(UUID | None, getattr(requester, "id", None))
    _ensure_group_membership(chat, requester_id)
    _ensure_group_owner(chat, requester_id)

    changed = False
    if name is not None and name.strip() and name.strip() != chat.name:
        setattr(chat, "name", name.strip())
        changed = True
    if avatar_url is not None:
        normalized_avatar = avatar_url.strip() or None
        if normalized_avatar != chat.avatar_url:
            setattr(chat, "avatar_url", normalized_avatar)
            changed = True

    if not changed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No changes provided")

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update group chat") from exc

    db.refresh(chat)
    return chat


def remove_group_members(
    db: Session,
    *,
    chat_id: UUID,
    requester: User,
    usernames: Sequence[str],
) -> GroupChat:
    normalized = [username.strip() for username in usernames if username and username.strip()]
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one username is required")

    chat = db.get(GroupChat, chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group chat not found")

    requester_id = cast(UUID | None, getattr(requester, "id", None))
    _ensure_group_membership(chat, requester_id)
    _ensure_group_owner(chat, requester_id)

    owner_uuid = _cast_uuid(cast(UUID | None, getattr(chat, "owner_id", None)))
    members_by_username = {member.username: member for member in chat.members if member.username}
    removed = False
    for username in normalized:
        member = members_by_username.get(username)
        if member is None:
            continue
        member_uuid = _cast_uuid(cast(UUID | None, getattr(member, "id", None)))
        if member_uuid == owner_uuid:
            continue
        chat.members.remove(member)
        removed = True

    if not removed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No members were removed")

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update members") from exc

    db.refresh(chat)
    return chat


__all__ = [
    "create_group_chat",
    "send_message",
    "list_messages",
    "delete_message",
    "delete_old_messages",
    "list_group_chats",
    "get_group_chat",
    "add_group_members",
    "update_group_chat",
    "remove_group_members",
]


def _notify_direct_message(
    db: Session,
    *,
    sender: User,
    recipient_id: UUID,
    message: Message,
    plaintext_preview: str | None = None,
) -> None:
    if recipient_id == sender.id:
        return
    preview = (plaintext_preview or "").strip()
    if not preview:
        encrypted_value = cast(str | None, getattr(message, "content", None))
        if encrypted_value:
            try:
                preview = vault_decrypt_text(encrypted_value).strip()
            except DataVaultError:
                preview = ""
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


def _cast_uuid(value: UUID | None) -> UUID:
    if value is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Missing identifier")
    return cast(UUID, value)


def _ensure_group_membership(chat: GroupChat, user_id: UUID | None) -> None:
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Membership required")
    member_ids = {_cast_uuid(member.id) for member in chat.members}
    if _cast_uuid(user_id) not in member_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not part of this group chat")


def _ensure_group_owner(chat: GroupChat, user_id: UUID | None) -> None:
    owner_id = cast(UUID | None, getattr(chat, "owner_id", None))
    if owner_id is None or user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Group owner permissions required")
    if _cast_uuid(owner_id) != _cast_uuid(user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Group owner permissions required")
