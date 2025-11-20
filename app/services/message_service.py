"""Messaging domain services."""
from __future__ import annotations

from typing import List

from fastapi import HTTPException, status

from ..database import FakeDatabase
from ..models import GroupChatRecord, MessageRecord, UserRecord
from ..schemas import GroupChatCreate, MessageSendRequest


def create_group_chat(db: FakeDatabase, owner: UserRecord, payload: GroupChatCreate) -> GroupChatRecord:
    members = list(dict.fromkeys([owner.username, *payload.members]))
    record = GroupChatRecord(name=payload.name, owner=owner.username, members=members)
    db.create_group_chat(record)
    return record


def send_message(db: FakeDatabase, sender: UserRecord, payload: MessageSendRequest) -> MessageRecord:
    record = MessageRecord(
        chat_id=payload.chat_id,
        sender=sender.username,
        content=payload.content,
        attachments=payload.attachments,
    )
    chat = db.get_group_chat(payload.chat_id)
    if chat and sender.username not in chat.members:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this chat")
    if chat:
        chat.updated_at = record.created_at
    db.create_message(record)
    return record


def list_messages(db: FakeDatabase, chat_id: str) -> List[MessageRecord]:
    messages = db.list_messages(chat_id)
    return sorted(messages, key=lambda message: message.created_at)


__all__ = ["create_group_chat", "send_message", "list_messages"]
