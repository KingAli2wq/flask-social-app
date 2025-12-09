"""Messaging API routes."""
from __future__ import annotations

import json
from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.websockets import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import Friendship, GroupChat, Message, User
from ..schemas import (
    DirectThreadResponse,
    GroupChatCreate,
    GroupChatInviteRequest,
    GroupChatMemberRemoveRequest,
    GroupChatResponse,
    GroupChatUpdateRequest,
    MessageResponse,
    MessageSendRequest,
    MessageThreadResponse,
)
from ..security.data_vault import DataVaultError, decrypt_structured, decrypt_text as vault_decrypt_text
from ..services import (
    add_group_members,
    create_group_chat,
    decode_access_token,
    delete_message,
    get_current_user,
    get_group_chat,
    list_group_chats,
    list_messages,
    remove_group_members,
    require_friendship,
    send_message,
    update_group_chat,
)
from ..services.group_crypto import GroupEncryptionError, decrypt_group_payload
from ..services.message_stream import message_stream_manager
from ..services.moderation_service import ModerationResult, moderate_text

router = APIRouter(prefix="/messages", tags=["messages"])


def _resolve_message_content(message: Message, fallback_chat: GroupChat | None = None) -> str:
    content = cast(str | None, message.content) or ""
    chat = message.group_chat or fallback_chat
    if not content:
        return ""
    if chat is not None:
        try:
            return decrypt_group_payload(chat.encryption_key, content)
        except GroupEncryptionError:
            return "[unable to decrypt message]"
    try:
        return vault_decrypt_text(content)
    except DataVaultError:
        return "[unable to decrypt message]"


def _resolve_message_attachments(message: Message, fallback_chat: GroupChat | None = None) -> list[str]:
    payload: Any = message.attachments
    if not payload:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, str)]
    if not isinstance(payload, dict) or "ciphertext" not in payload:
        return []
    ciphertext = payload.get("ciphertext")
    if not isinstance(ciphertext, str):
        return []
    scheme = payload.get("scheme")
    encoding = payload.get("encoding")
    if scheme == "group.v1" and encoding == "json":
        chat = message.group_chat or fallback_chat
        if chat is None:
            return []
        try:
            decrypted = decrypt_group_payload(chat.encryption_key, ciphertext)
        except GroupEncryptionError:
            return []
        try:
            data = json.loads(decrypted)
        except json.JSONDecodeError:
            return []
        return [item for item in data if isinstance(item, str)]
    try:
        data = decrypt_structured(payload)
    except DataVaultError:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, str)]
    return []


def _sender_display_name(user: User | None) -> str | None:
    if user is None:
        return None
    return user.display_name or user.username


def _to_message_response(message: Message) -> MessageResponse:
    attachments = _resolve_message_attachments(message)
    parent = message.parent
    reply_payload = None
    content = _resolve_message_content(message)
    sender = message.sender
    sender_username = sender.username if sender else None
    sender_display = _sender_display_name(sender)
    sender_avatar_url = sender.avatar_url if sender else None
    if parent is not None:
        parent_sender = parent.sender
        reply_payload = {
            "id": parent.id,
            "sender_id": parent.sender_id,
            "sender_username": parent_sender.username if parent_sender else None,
            "sender_display_name": _sender_display_name(parent_sender),
            "sender_avatar_url": parent_sender.avatar_url if parent_sender else None,
            "content": None if parent.is_deleted else _resolve_message_content(parent, message.group_chat),
            "is_deleted": parent.is_deleted,
        }
    return MessageResponse(
        id=message.id,
        chat_id=message.chat_id,
        sender_id=message.sender_id,
        recipient_id=message.recipient_id,
        content=content,
        attachments=attachments,
        created_at=message.created_at,
        sender_username=sender_username,
        sender_display_name=sender_display,
        sender_avatar_url=sender_avatar_url,
        reply_to=reply_payload,
        is_deleted=message.is_deleted,
        deleted_at=message.deleted_at,
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
        owner_id=chat.owner_id,
        members=members,
        avatar_url=chat.avatar_url,
        lock_code=chat.lock_code,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


@router.post("/send", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message_endpoint(
    payload: MessageSendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> MessageResponse:
    moderation: ModerationResult = moderate_text(payload.content or "")
    if not moderation.is_allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Your message violates our community guidelines.",
                "reasons": moderation.reasons,
            },
        )

    record = send_message(db, sender=current_user, payload=payload)
    response = _to_message_response(record)
    await _broadcast_message(response)
    return response


@router.delete("/{message_id}", response_model=MessageResponse)
async def delete_message_endpoint(
    message_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> MessageResponse:
    record = delete_message(db, message_id=message_id, requester=current_user)
    response = _to_message_response(record)
    await _broadcast_message(response, event_type="message.deleted")
    return response


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


@router.get("/groups", response_model=list[GroupChatResponse])
async def list_groups_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[GroupChatResponse]:
    chats = list_group_chats(db, user=current_user)
    return [_to_group_response(chat) for chat in chats]


@router.get("/groups/{group_id}", response_model=GroupChatResponse)
async def group_detail_endpoint(
    group_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> GroupChatResponse:
    chat = get_group_chat(db, chat_id=group_id, requester=current_user)
    return _to_group_response(chat)


@router.post("/groups/{group_id}/members", response_model=GroupChatResponse)
async def invite_group_members_endpoint(
    group_id: UUID,
    payload: GroupChatInviteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> GroupChatResponse:
    chat = add_group_members(db, chat_id=group_id, requester=current_user, usernames=payload.members)
    return _to_group_response(chat)


@router.patch("/groups/{group_id}", response_model=GroupChatResponse)
async def update_group_endpoint(
    group_id: UUID,
    payload: GroupChatUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> GroupChatResponse:
    chat = update_group_chat(
        db,
        chat_id=group_id,
        requester=current_user,
        name=payload.name,
        avatar_url=payload.avatar_url,
    )
    return _to_group_response(chat)


@router.post("/groups/{group_id}/members/remove", response_model=GroupChatResponse)
async def remove_group_members_endpoint(
    group_id: UUID,
    payload: GroupChatMemberRemoveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> GroupChatResponse:
    chat = remove_group_members(db, chat_id=group_id, requester=current_user, usernames=payload.members)
    return _to_group_response(chat)


@router.get("/{chat_id}", response_model=MessageThreadResponse)
async def thread_endpoint(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> MessageThreadResponse:
    messages = list_messages(db, chat_id=chat_id)
    return MessageThreadResponse(chat_id=chat_id, messages=[_to_message_response(item) for item in messages])


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


async def _broadcast_message(message: MessageResponse, event_type: str = "message.created") -> None:
    await message_stream_manager.broadcast(
        message.chat_id,
        {
            "type": event_type,
            "chat_id": message.chat_id,
            "message": message.model_dump(),
        },
    )
