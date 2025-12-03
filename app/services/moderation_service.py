"""Moderation-specific business logic for dashboards and role management."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import MediaAsset, Post, PostComment, PostDislike, PostLike, User
from ..schemas import (
    ModerationDashboardResponse,
    ModerationPostSummary,
    ModerationStats,
    ModerationUserSummary,
)

_VALID_ROLES = {"owner", "admin", "user"}


def load_moderation_dashboard(db: Session, *, recent_limit: int = 8) -> ModerationDashboardResponse:
    """Return high level stats plus the most recent users/posts for review."""

    now = datetime.now(timezone.utc)
    active_cutoff = now - timedelta(hours=24)

    total_users = int(db.scalar(select(func.count(User.id))) or 0)
    active_last_24h = int(
        db.scalar(select(func.count(User.id)).where(User.last_active_at >= active_cutoff)) or 0
    )
    total_posts = int(db.scalar(select(func.count(Post.id))) or 0)
    total_media_assets = int(db.scalar(select(func.count(MediaAsset.id))) or 0)

    stats = ModerationStats(
        total_users=total_users,
        active_last_24h=active_last_24h,
        total_posts=total_posts,
        total_media_assets=total_media_assets,
    )

    post_counts_subquery = (
        db.query(Post.user_id.label("user_id"), func.count(Post.id).label("post_count"))
        .group_by(Post.user_id)
        .subquery()
    )

    recent_user_rows: Iterable[tuple[User, int]] = (
        db.query(
            User,
            func.coalesce(post_counts_subquery.c.post_count, 0).label("post_count"),
        )
        .outerjoin(post_counts_subquery, User.id == post_counts_subquery.c.user_id)
        .order_by(User.created_at.desc())
        .limit(recent_limit)
        .all()
    )
    recent_users = [
        _summarize_user(user, int(post_count or 0))
        for user, post_count in recent_user_rows
    ]

    recent_post_rows: Iterable[tuple[Post, User, int, int, int]] = (
        db.query(
            Post,
            User,
            func.count(func.distinct(PostLike.id)).label("like_count"),
            func.count(func.distinct(PostDislike.id)).label("dislike_count"),
            func.count(func.distinct(PostComment.id)).label("comment_count"),
        )
        .join(User, Post.user_id == User.id)
        .outerjoin(PostLike, PostLike.post_id == Post.id)
        .outerjoin(PostDislike, PostDislike.post_id == Post.id)
        .outerjoin(PostComment, PostComment.post_id == Post.id)
        .group_by(Post.id, User.id)
        .order_by(Post.created_at.desc())
        .limit(recent_limit)
        .all()
    )

    recent_posts = [
        _summarize_post(post, author, int(likes or 0), int(dislikes or 0), int(comments or 0))
        for post, author, likes, dislikes, comments in recent_post_rows
    ]

    return ModerationDashboardResponse(stats=stats, recent_users=recent_users, recent_posts=recent_posts)


def update_user_role(
    db: Session,
    *,
    actor: User,
    target_user_id: UUID,
    new_role: str,
) -> ModerationUserSummary:
    """Allow an owner to promote/demote another account."""

    desired_role = (new_role or "user").lower()
    if desired_role not in _VALID_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown role")

    actor_role = (getattr(actor, "role", None) or "user").lower()
    if actor_role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners can change roles")

    target = db.get(User, target_user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target_role = (getattr(target, "role", None) or "user").lower()

    if target_role == "owner" and desired_role != "owner":
        remaining = int(
            db.scalar(select(func.count(User.id)).where(User.role == "owner", User.id != target.id)) or 0
        )
        if remaining == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="App needs at least one owner")

    if target.id == actor.id and desired_role != "owner":
        remaining = int(
            db.scalar(select(func.count(User.id)).where(User.role == "owner", User.id != actor.id)) or 0
        )
        if remaining == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot demote the final owner")

    target.role = desired_role

    db.commit()
    db.refresh(target)

    post_count = int(db.scalar(select(func.count(Post.id)).where(Post.user_id == target.id)) or 0)
    return _summarize_user(target, post_count)


def _summarize_user(user: User, post_count: int) -> ModerationUserSummary:
    return ModerationUserSummary(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        role=user.role,
        post_count=post_count,
        created_at=user.created_at,
        last_active_at=user.last_active_at,
        email_verified=bool(user.email_verified_at),
    )


def _summarize_post(
    post: Post,
    author: User,
    like_count: int,
    dislike_count: int,
    comment_count: int,
) -> ModerationPostSummary:
    return ModerationPostSummary(
        id=post.id,
        caption=post.caption,
        created_at=post.created_at,
        user_id=post.user_id,
        username=author.username,
        display_name=author.display_name,
        role=author.role,
        media_asset_id=post.media_asset_id,
        media_url=post.media_url,
        like_count=like_count,
        dislike_count=dislike_count,
        comment_count=comment_count,
    )


__all__ = ["load_moderation_dashboard", "update_user_role"]
