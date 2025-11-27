"""Business logic for follower relationships."""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import Follow, User


@dataclass(slots=True)
class FollowStats:
    user_id: UUID
    followers_count: int
    following_count: int
    is_following: bool


def _get_user_or_404(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def follow_user(db: Session, *, follower: User, target_id: UUID) -> bool:
    follower_id = cast(UUID, follower.id)
    if follower_id == target_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot follow yourself")

    _get_user_or_404(db, target_id)

    existing = db.scalar(
        select(Follow).where(Follow.follower_id == follower_id, Follow.following_id == target_id)
    )
    if existing is not None:
        return False

    record = Follow(follower_id=follower_id, following_id=target_id)
    db.add(record)
    try:
        db.commit()
    except SQLAlchemyError as exc:  # pragma: no cover - database errors
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to follow user") from exc
    return True


def unfollow_user(db: Session, *, follower: User, target_id: UUID) -> bool:
    follower_id = cast(UUID, follower.id)
    if follower_id == target_id:
        return False

    record = db.scalar(
        select(Follow).where(Follow.follower_id == follower_id, Follow.following_id == target_id)
    )
    if record is None:
        return False
    try:
        db.delete(record)
        db.commit()
        return True
    except SQLAlchemyError as exc:  # pragma: no cover - database errors
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to unfollow user") from exc


def get_follow_stats(db: Session, *, user_id: UUID, viewer_id: UUID | None = None) -> FollowStats:
    _get_user_or_404(db, user_id)

    followers_count = db.scalar(
        select(func.count()).select_from(Follow).where(Follow.following_id == user_id)
    ) or 0
    following_count = db.scalar(
        select(func.count()).select_from(Follow).where(Follow.follower_id == user_id)
    ) or 0

    is_following = False
    if viewer_id is not None:
        is_following = (
            db.scalar(
                select(Follow.follower_id).where(
                    Follow.follower_id == viewer_id,
                    Follow.following_id == user_id,
                )
            )
            is not None
        )

    return FollowStats(
        user_id=user_id,
        followers_count=int(followers_count),
        following_count=int(following_count),
        is_following=is_following,
    )


__all__ = ["FollowStats", "follow_user", "unfollow_user", "get_follow_stats"]
