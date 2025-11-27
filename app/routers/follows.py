"""Follow management API routes."""
from __future__ import annotations

from dataclasses import asdict
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User
from ..schemas import FollowActionResponse, FollowStatsResponse
from ..services import (
    follow_user,
    get_current_user,
    get_follow_stats,
    get_optional_user,
    unfollow_user,
)

router = APIRouter(prefix="/follows", tags=["follows"])


@router.post("/{target_id}", response_model=FollowActionResponse, status_code=status.HTTP_201_CREATED)
async def follow_user_endpoint(
    target_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FollowActionResponse:
    viewer_id = cast(UUID, current_user.id)
    changed = follow_user(db, follower=current_user, target_id=target_id)
    stats = get_follow_stats(db, user_id=target_id, viewer_id=viewer_id)
    payload = asdict(stats)
    payload["status"] = "followed" if changed else "noop"
    return FollowActionResponse(**payload)


@router.delete("/{target_id}", response_model=FollowActionResponse)
async def unfollow_user_endpoint(
    target_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FollowActionResponse:
    viewer_id = cast(UUID, current_user.id)
    changed = unfollow_user(db, follower=current_user, target_id=target_id)
    stats = get_follow_stats(db, user_id=target_id, viewer_id=viewer_id)
    payload = asdict(stats)
    payload["status"] = "unfollowed" if changed else "noop"
    return FollowActionResponse(**payload)


@router.get("/stats/{user_id}", response_model=FollowStatsResponse)
async def follow_stats_endpoint(
    user_id: UUID,
    db: Session = Depends(get_session),
    viewer: User | None = Depends(get_optional_user),
) -> FollowStatsResponse:
    viewer_id = cast(UUID, viewer.id) if viewer else None
    stats = get_follow_stats(db, user_id=user_id, viewer_id=viewer_id)
    return FollowStatsResponse(**asdict(stats))
