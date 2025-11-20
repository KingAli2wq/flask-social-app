"""Notification API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from ..database import FakeDatabase, get_database
from ..models import NotificationRecord, UserRecord
from ..schemas import NotificationListResponse, NotificationResponse
from ..services import add_notification, get_current_user, list_notifications, mark_all_read

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _to_notification_response(record: NotificationRecord) -> NotificationResponse:
    return NotificationResponse(
        id=record.id,
        body=record.body,
        created_at=record.created_at,
        read=record.read,
    )


@router.get("/", response_model=NotificationListResponse)
async def list_my_notifications(
    current_user: UserRecord = Depends(get_current_user),
    db: FakeDatabase = Depends(get_database),
) -> NotificationListResponse:
    records = list_notifications(db, current_user.username)
    return NotificationListResponse(items=[_to_notification_response(item) for item in records])


@router.post("/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    body: str,
    current_user: UserRecord = Depends(get_current_user),
    db: FakeDatabase = Depends(get_database),
) -> NotificationResponse:
    record = add_notification(db, current_user.username, body)
    return _to_notification_response(record)


@router.post("/mark-read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notifications_read(
    current_user: UserRecord = Depends(get_current_user),
    db: FakeDatabase = Depends(get_database),
) -> None:
    mark_all_read(db, current_user.username)
