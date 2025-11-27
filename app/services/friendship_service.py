"""Business logic for friend requests and friendships."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
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


def list_friends(db: Session, *, user: User) -> Sequence[Friendship]:
    stmt = select(Friendship).where(or_(Friendship.user_a_id == user.id, Friendship.user_b_id == user.id)).order_by(Friendship.created_at.asc())
    return db.scalars(stmt).all()


def send_friend_request(db: Session, *, sender: User, recipient_username: str) -> FriendRequest:
    candidate = recipient_username.strip().lower()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username required")

    recipient = db.scalar(select(User).where(User.username.ilike(candidate)))
    if recipient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if recipient.id == sender.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot befriend yourself")

    if _existing_friendship(db, sender.id, recipient.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already friends")

    pending = db.scalar(
        select(FriendRequest).where(
            or_(
                and_(FriendRequest.sender_id == sender.id, FriendRequest.recipient_id == recipient.id, FriendRequest.status == "pending"),
                and_(FriendRequest.sender_id == recipient.id, FriendRequest.recipient_id == sender.id, FriendRequest.status == "pending"),
            )
        )
    )
    if pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pending request already exists")

    request = FriendRequest(sender_id=sender.id, recipient_id=recipient.id)
    try:
        db.add(request)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send request") from exc

    db.refresh(request)
    return request


def list_friend_requests(db: Session, *, user: User) -> tuple[list[FriendRequest], list[FriendRequest]]:
    incoming_stmt = select(FriendRequest).where(FriendRequest.recipient_id == user.id, FriendRequest.status == "pending")
    outgoing_stmt = select(FriendRequest).where(FriendRequest.sender_id == user.id, FriendRequest.status == "pending")
    incoming = db.scalars(incoming_stmt).all()
    outgoing = db.scalars(outgoing_stmt).all()
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
    if request is None or request.recipient_id != recipient.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if request.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request already processed")

    request.status = "accepted" if accept else "declined"
    request.responded_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update request") from exc
    db.refresh(request)

    if accept:
        friendship = _existing_friendship(db, request.sender_id, request.recipient_id)
        if friendship is None:
            friendship = _create_friendship(db, request.sender_id, request.recipient_id)
        return friendship
    return None


def require_friendship(db: Session, *, user: User, friend_id: UUID) -> tuple[Friendship, User]:
    friend = db.get(User, friend_id)
    if friend is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Friend not found")
    friendship = _existing_friendship(db, user.id, friend.id)
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
