"""Notification API routes."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import Notification, User
from ..schemas import NotificationListResponse, NotificationResponse, NotificationSummaryResponse
from ..services import (
    add_notification,
    count_unread_notifications,
    decode_access_token,
    get_current_user,
    list_notifications,
    mark_all_read,
)
from ..services.notification_stream import notification_stream_manager

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _to_notification_response(record: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=record.id,
        recipient_id=record.recipient_id,
        sender_id=record.sender_id,
        type=record.type,
        content=record.content,
        created_at=record.created_at,
        read=record.read,
    )


@router.get("/", response_model=NotificationListResponse)
async def list_my_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> NotificationListResponse:
    records = list_notifications(db, current_user.id)
    return NotificationListResponse(items=[_to_notification_response(item) for item in records])


@router.post("/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    content: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> NotificationResponse:
    try:
        record = add_notification(db, recipient_id=current_user.id, content=content, sender_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_notification_response(record)


@router.post("/mark-read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> None:
    mark_all_read(db, current_user.id)


@router.get("/summary", response_model=NotificationSummaryResponse)
async def notification_summary_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> NotificationSummaryResponse:
    unread = count_unread_notifications(db, current_user.id)
    return NotificationSummaryResponse(unread_count=unread)


@router.websocket("/ws")
async def notifications_socket(
    websocket: WebSocket,
    token: str = Query(..., alias="token"),
) -> None:
    try:
        user_id = decode_access_token(token)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await notification_stream_manager.connect(str(user_id), websocket)
    await websocket.send_text(json.dumps({"type": "ready"}))
    try:
        while True:
            try:
                payload = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            if payload.strip().lower() == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    finally:
        await notification_stream_manager.disconnect(websocket)
