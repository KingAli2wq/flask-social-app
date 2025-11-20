"""Messaging API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from ..database import FakeDatabase, get_database
from ..models import GroupChatRecord, MessageRecord, UserRecord
from ..schemas import (
    GroupChatCreate,
    GroupChatResponse,
    MessageResponse,
    MessageSendRequest,
    MessageThreadResponse,
)
from ..services import create_group_chat, get_current_user, list_messages, send_message

router = APIRouter(prefix="/messages", tags=["messages"])


def _to_message_response(message: MessageRecord) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        chat_id=message.chat_id,
        sender=message.sender,
        content=message.content,
        attachments=message.attachments,
        created_at=message.created_at,
    )


def _to_group_response(chat: GroupChatRecord) -> GroupChatResponse:
    return GroupChatResponse(
        id=chat.id,
        name=chat.name,
        owner=chat.owner,
        members=chat.members,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


@router.post("/send", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message_endpoint(
    payload: MessageSendRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: FakeDatabase = Depends(get_database),
) -> MessageResponse:
    record = send_message(db, current_user, payload)
    return _to_message_response(record)


@router.get("/{chat_id}", response_model=MessageThreadResponse)
async def thread_endpoint(
    chat_id: str,
    current_user: UserRecord = Depends(get_current_user),
    db: FakeDatabase = Depends(get_database),
) -> MessageThreadResponse:
    messages = list_messages(db, chat_id)
    return MessageThreadResponse(chat_id=chat_id, messages=[_to_message_response(item) for item in messages])


@router.post("/groups", response_model=GroupChatResponse, status_code=status.HTTP_201_CREATED)
async def create_group_endpoint(
    payload: GroupChatCreate,
    current_user: UserRecord = Depends(get_current_user),
    db: FakeDatabase = Depends(get_database),
) -> GroupChatResponse:
    chat = create_group_chat(db, current_user, payload)
    return _to_group_response(chat)
