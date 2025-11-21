"""Notification API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import Notification, User
from ..schemas import NotificationListResponse, NotificationResponse
from ..services import add_notification, get_current_user, list_notifications, mark_all_read

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _to_notification_response(record: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=record.id,
        recipient_id=record.recipient_id,
        actor_id=record.actor_id,
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
        record = add_notification(db, recipient_id=current_user.id, content=content, actor_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_notification_response(record)


@router.post("/mark-read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> None:
    mark_all_read(db, current_user.id)
