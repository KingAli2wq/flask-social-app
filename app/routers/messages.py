"""Messaging API routes."""
from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.websockets import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import Friendship, GroupChat, Message, User
from ..schemas import (
    DirectThreadResponse,
    GroupChatCreate,
    GroupChatResponse,
    MessageResponse,
    MessageSendRequest,
    MessageThreadResponse,
)
from ..services import (
    create_group_chat,
    decode_access_token,
    get_current_user,
    list_messages,
    require_friendship,
    send_message,
)
from ..services.message_stream import message_stream_manager

router = APIRouter(prefix="/messages", tags=["messages"])


def _to_message_response(message: Message) -> MessageResponse:
    attachments = message.attachments or []
    return MessageResponse(
        id=message.id,
        chat_id=message.chat_id,
        sender_id=message.sender_id,
        recipient_id=message.recipient_id,
        content=message.content,
        attachments=attachments,
        created_at=message.created_at,
    )


def _to_group_response(chat: GroupChat) -> GroupChatResponse:
    owner_username = chat.owner.username if chat.owner else ""
    members: list[str] = []
    for member in chat.members:
        username = member.username
        if username not in members:
            members.append(username)
    if owner_username:
        if owner_username in members:
            members.remove(owner_username)
        members.insert(0, owner_username)
    return GroupChatResponse(
        id=chat.id,
        name=chat.name,
        owner=owner_username,
        members=members,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


@router.post("/send", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message_endpoint(
    payload: MessageSendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> MessageResponse:
    record = send_message(db, sender=current_user, payload=payload)
    response = _to_message_response(record)
    await _broadcast_message(response)
    return response


@router.get("/{chat_id}", response_model=MessageThreadResponse)
async def thread_endpoint(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> MessageThreadResponse:
    messages = list_messages(db, chat_id=chat_id)
    return MessageThreadResponse(chat_id=chat_id, messages=[_to_message_response(item) for item in messages])


@router.get("/direct/{friend_id}", response_model=DirectThreadResponse)
async def direct_thread_endpoint(
    friend_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> DirectThreadResponse:
    friendship, friend = require_friendship(db, user=current_user, friend_id=friend_id)
    messages = list_messages(db, chat_id=friendship.thread_id)
    return DirectThreadResponse(
        chat_id=friendship.thread_id,
        friend_id=friend.id,
        friend_username=friend.username,
        friend_avatar_url=friend.avatar_url,
        lock_code=friendship.lock_code,
        messages=[_to_message_response(item) for item in messages],
    )


@router.post("/groups", response_model=GroupChatResponse, status_code=status.HTTP_201_CREATED)
async def create_group_endpoint(
    payload: GroupChatCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> GroupChatResponse:
    chat = create_group_chat(db, current_user, payload)
    return _to_group_response(chat)


@router.websocket("/ws/{chat_id}")
async def message_thread_socket(
    websocket: WebSocket,
    chat_id: str,
    token: str = Query(..., alias="token"),
    db: Session = Depends(get_session),
) -> None:
    try:
        user_id = decode_access_token(token)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not _user_can_access_chat(db, chat_id, user_id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await message_stream_manager.connect(chat_id, websocket)
    await websocket.send_text(json.dumps({"type": "ready", "chat_id": chat_id}))
    try:
        while True:
            try:
                payload = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            if payload.strip().lower() == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "chat_id": chat_id}))
    finally:
        await message_stream_manager.disconnect(websocket)


def _user_can_access_chat(db: Session, chat_id: str, user_id: UUID) -> bool:
    friendship = db.scalar(select(Friendship).where(Friendship.thread_id == chat_id))
    if friendship is not None and friendship.involves(user_id):
        return True
    try:
        chat_uuid = UUID(chat_id)
    except ValueError:
        return False
    membership_stmt = select(GroupChat.id).where(GroupChat.id == chat_uuid, GroupChat.members.any(User.id == user_id))
    chat = db.scalar(membership_stmt)
    return chat is not None


async def _broadcast_message(message: MessageResponse) -> None:
    await message_stream_manager.broadcast(
        message.chat_id,
        {
            "type": "message.created",
            "chat_id": message.chat_id,
            "message": message.model_dump(),
        },
    )
