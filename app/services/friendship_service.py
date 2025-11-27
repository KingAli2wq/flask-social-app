"""Business logic for friend requests and friendships."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import FriendRequest, Friendship, User


def _ordered_pair(a: UUID, b: UUID) -> tuple[UUID, UUID]:
    return (a, b) if str(a) < str(b) else (b, a)


def _existing_friendship(db: Session, user_id: UUID, friend_id: UUID) -> Friendship | None:
    first, second = _ordered_pair(user_id, friend_id)
    stmt = select(Friendship).where(and_(Friendship.user_a_id == first, Friendship.user_b_id == second))
    return db.scalars(stmt).first()


def list_friends(db: Session, *, user: User) -> list[Friendship]:
    user_id = cast(UUID, user.id)
    stmt = select(Friendship).where(or_(Friendship.user_a_id == user_id, Friendship.user_b_id == user_id)).order_by(Friendship.created_at.asc())
    return list(db.scalars(stmt))


def send_friend_request(db: Session, *, sender: User, recipient_username: str) -> FriendRequest:
    sender_id = cast(UUID, sender.id)
    candidate = recipient_username.strip().lower()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username required")

    recipient = db.scalar(select(User).where(User.username.ilike(candidate)))
    if recipient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    recipient_id = cast(UUID, recipient.id)
    if recipient_id == sender_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot befriend yourself")

    if _existing_friendship(db, sender_id, recipient_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already friends")

    pending = db.scalar(
        select(FriendRequest).where(
            or_(
                and_(FriendRequest.sender_id == sender_id, FriendRequest.recipient_id == recipient_id, FriendRequest.status == "pending"),
                and_(FriendRequest.sender_id == recipient_id, FriendRequest.recipient_id == sender_id, FriendRequest.status == "pending"),
            )
        )
    )
    if pending is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pending request already exists")

    request = FriendRequest(sender_id=sender_id, recipient_id=recipient_id)
    try:
        db.add(request)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send request") from exc

    db.refresh(request)
    return request


def list_friend_requests(db: Session, *, user: User) -> tuple[list[FriendRequest], list[FriendRequest]]:
    user_id = cast(UUID, user.id)
    incoming_stmt = select(FriendRequest).where(FriendRequest.recipient_id == user_id, FriendRequest.status == "pending")
    outgoing_stmt = select(FriendRequest).where(FriendRequest.sender_id == user_id, FriendRequest.status == "pending")
    incoming = list(db.scalars(incoming_stmt))
    outgoing = list(db.scalars(outgoing_stmt))
    return incoming, outgoing


def _create_friendship(db: Session, first: UUID, second: UUID) -> Friendship:
    user_a_id, user_b_id = _ordered_pair(first, second)
    friendship = Friendship(user_a_id=user_a_id, user_b_id=user_b_id)
    try:
        db.add(friendship)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create friendship") from exc
    db.refresh(friendship)
    return friendship


def respond_to_request(db: Session, *, request_id: UUID, recipient: User, accept: bool) -> Friendship | None:
    request = db.get(FriendRequest, request_id)
    recipient_id = cast(UUID, recipient.id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    stored_recipient_id = cast(UUID, request.recipient_id)
    if stored_recipient_id != recipient_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    status_value = cast(str, request.status)
    if status_value != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request already processed")

    setattr(request, "status", "accepted" if accept else "declined")
    setattr(request, "responded_at", datetime.now(timezone.utc))

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update request") from exc
    db.refresh(request)

    if accept:
        sender_id = cast(UUID, request.sender_id)
        friendship = _existing_friendship(db, sender_id, stored_recipient_id)
        if friendship is None:
            friendship = _create_friendship(db, sender_id, stored_recipient_id)
        return friendship
    return None


def require_friendship(db: Session, *, user: User, friend_id: UUID) -> tuple[Friendship, User]:
    friend = db.get(User, friend_id)
    if friend is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Friend not found")
    user_id = cast(UUID, user.id)
    friend_uuid = cast(UUID, friend.id)
    friendship = _existing_friendship(db, user_id, friend_uuid)
    if friendship is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Friendship required")
    return friendship, friend


__all__ = [
    "list_friends",
    "send_friend_request",
    "list_friend_requests",
    "respond_to_request",
    "require_friendship",
]
