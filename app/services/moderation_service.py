"""Moderation-specific business logic for dashboards and role management."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import (
    Follow,
    MediaAsset,
    MediaComment,
    MediaDislike,
    MediaLike,
    Post,
    PostComment,
    PostDislike,
    PostLike,
    User,
)
from ..schemas import (
    ModerationDashboardResponse,
    ModerationMediaDetail,
    ModerationMediaList,
    ModerationMediaSummary,
    ModerationPostDetail,
    ModerationPostList,
    ModerationPostSummary,
    ModerationStats,
    ModerationUserDetail,
    ModerationUserList,
    ModerationUserSummary,
)
from .spaces_service import SpacesDeletionError, delete_file_from_spaces

_VALID_ROLES = {"owner", "admin", "user"}
MAX_PAGE_LIMIT = 100

logger = logging.getLogger(__name__)


def _normalize_pagination(skip: int | None, limit: int | None) -> tuple[int, int]:
    safe_skip = max(0, int(skip or 0))
    safe_limit = max(1, min(int(limit or 25), MAX_PAGE_LIMIT))
    return safe_skip, safe_limit


def _pagination_filter_from_search(model, search: str | None):
    if not search:
        return None
    pattern = f"%{search.lower()}%"
    if model is User:
        return or_(
            func.lower(User.username).like(pattern),
            func.lower(User.display_name).like(pattern),
            func.lower(User.email).like(pattern),
        )
    if model is Post:
        return func.lower(Post.caption).like(pattern)
    return or_(
        func.lower(MediaAsset.key).like(pattern),
        func.lower(MediaAsset.url).like(pattern),
        func.lower(User.username).like(pattern),
        func.lower(User.display_name).like(pattern),
    )


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

    recent_user_rows = (
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

    recent_post_rows = (
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


def list_moderation_users(
    db: Session,
    *,
    skip: int | None = None,
    limit: int | None = None,
    search: str | None = None,
    active_only: bool = False,
) -> ModerationUserList:
    safe_skip, safe_limit = _normalize_pagination(skip, limit)
    search_expr = _pagination_filter_from_search(User, search)
    active_cutoff = datetime.now(timezone.utc) - timedelta(hours=24) if active_only else None

    count_query = db.query(func.count(User.id))
    if search_expr is not None:
        count_query = count_query.filter(search_expr)
    if active_cutoff is not None:
        count_query = count_query.filter(User.last_active_at >= active_cutoff)
    total = int(count_query.scalar() or 0)

    post_counts = (
        db.query(Post.user_id.label("user_id"), func.count(Post.id).label("post_count"))
        .group_by(Post.user_id)
        .subquery()
    )
    media_counts = (
        db.query(MediaAsset.user_id.label("user_id"), func.count(MediaAsset.id).label("media_count"))
        .group_by(MediaAsset.user_id)
        .subquery()
    )

    query = (
        db.query(
            User,
            func.coalesce(post_counts.c.post_count, 0).label("post_count"),
            func.coalesce(media_counts.c.media_count, 0).label("media_count"),
        )
        .outerjoin(post_counts, User.id == post_counts.c.user_id)
        .outerjoin(media_counts, User.id == media_counts.c.user_id)
    )
    if search_expr is not None:
        query = query.filter(search_expr)
    if active_cutoff is not None:
        query = query.filter(User.last_active_at >= active_cutoff)

    rows = (
        query.order_by(User.created_at.desc()).offset(safe_skip).limit(safe_limit).all()
    )
    items = [
        _summarize_user(user, int(post_count or 0), media_count=int(media_count or 0))
        for user, post_count, media_count in rows
    ]
    return ModerationUserList(total=total, items=items)


def get_moderation_user(db: Session, *, user_id: UUID) -> ModerationUserDetail:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    post_count = int(db.scalar(select(func.count(Post.id)).where(Post.user_id == user.id)) or 0)
    media_count = int(db.scalar(select(func.count(MediaAsset.id)).where(MediaAsset.user_id == user.id)) or 0)
    follower_count = int(db.scalar(select(func.count(Follow.follower_id)).where(Follow.following_id == user.id)) or 0)
    following_count = int(db.scalar(select(func.count(Follow.following_id)).where(Follow.follower_id == user.id)) or 0)

    summary = _summarize_user(user, post_count, media_count=media_count)
    bio = cast(str | None, user.bio)
    location = cast(str | None, user.location)
    website = cast(str | None, user.website)
    allow_friend_requests = cast(bool | None, getattr(user, "allow_friend_requests", None))
    dm_followers_only = cast(bool | None, getattr(user, "dm_followers_only", None))
    return ModerationUserDetail(
        **summary.model_dump(),
        bio=bio,
        location=location,
        website=website,
        allow_friend_requests=allow_friend_requests,
        dm_followers_only=dm_followers_only,
        follower_count=follower_count,
        following_count=following_count,
    )


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
    target_id = cast(UUID, target.id)
    if target_role == "owner" and desired_role != "owner":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only the primary owner can hold this role")
    actor_id = cast(UUID, actor.id)

    if target_role == "owner" and desired_role != "owner":
        remaining = int(
            db.scalar(select(func.count(User.id)).where(User.role == "owner", User.id != target_id)) or 0
        )
        if remaining == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="App needs at least one owner")

    if target_id == actor_id and desired_role != "owner":
        remaining = int(
            db.scalar(select(func.count(User.id)).where(User.role == "owner", User.id != actor_id)) or 0
        )
        if remaining == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot demote the final owner")

    setattr(target, "role", desired_role)

    db.commit()
    db.refresh(target)

    post_count = int(db.scalar(select(func.count(Post.id)).where(Post.user_id == target_id)) or 0)
    media_count = int(db.scalar(select(func.count(MediaAsset.id)).where(MediaAsset.user_id == target_id)) or 0)
    return _summarize_user(target, post_count, media_count=media_count)


def update_moderation_user(
    db: Session,
    *,
    user_id: UUID,
    payload: dict[str, object],
) -> ModerationUserDetail:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    changed = False

    def _assign_text(attr: str) -> None:
        nonlocal changed
        if attr not in payload:
            return
        value = payload.get(attr)
        if value is None:
            setattr(user, attr, None)
        else:
            text = str(value).strip()
            setattr(user, attr, text or None)
        changed = True

    for field in ("display_name", "bio", "location", "website"):
        _assign_text(field)

    if "avatar_url" in payload:
        setattr(user, "avatar_url", payload.get("avatar_url") or None)
        changed = True
    if "email" in payload:
        setattr(user, "email", payload.get("email") or None)
        changed = True
    if "allow_friend_requests" in payload and payload["allow_friend_requests"] is not None:
        setattr(user, "allow_friend_requests", bool(payload["allow_friend_requests"]))
        changed = True
    if "dm_followers_only" in payload and payload["dm_followers_only"] is not None:
        setattr(user, "dm_followers_only", bool(payload["dm_followers_only"]))
        changed = True

    if not changed:
        return get_moderation_user(db, user_id=cast(UUID, user.id))

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update profile") from exc

    db.refresh(user)
    return get_moderation_user(db, user_id=cast(UUID, user.id))


def delete_moderation_user(db: Session, *, actor: User, user_id: UUID) -> None:
    actor_id = cast(UUID, actor.id)
    if actor_id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own profile")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target_role = (getattr(user, "role", "user") or "user").lower()
    target_id = cast(UUID, user.id)
    if target_role == "owner":
        remaining = int(db.scalar(select(func.count(User.id)).where(User.role == "owner", User.id != target_id)) or 0)
        if remaining == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete the final owner")

    assets = list(db.query(MediaAsset).where(MediaAsset.user_id == target_id).all())
    for asset in assets:
        asset_key = cast(str | None, asset.key)
        if not asset_key:
            continue
        try:
            delete_file_from_spaces(asset_key)
        except SpacesDeletionError as exc:
            logger.warning("Failed to delete asset %s for user %s: %s", asset.id, target_id, exc)

    try:
        db.delete(user)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete user") from exc


def list_moderation_posts(
    db: Session,
    *,
    skip: int | None = None,
    limit: int | None = None,
    user_id: UUID | None = None,
    search: str | None = None,
) -> ModerationPostList:
    safe_skip, safe_limit = _normalize_pagination(skip, limit)
    filters = []
    if user_id is not None:
        filters.append(Post.user_id == user_id)
    caption_filter = _pagination_filter_from_search(Post, search)
    if caption_filter is not None:
        filters.append(caption_filter)

    count_query = db.query(func.count(Post.id))
    for condition in filters:
        count_query = count_query.filter(condition)
    total = int(count_query.scalar() or 0)

    statement = (
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
    )
    for condition in filters:
        statement = statement.filter(condition)

    rows = statement.order_by(Post.created_at.desc()).offset(safe_skip).limit(safe_limit).all()
    items = [
        _summarize_post(post, author, int(likes or 0), int(dislikes or 0), int(comments or 0))
        for post, author, likes, dislikes, comments in rows
    ]
    return ModerationPostList(total=total, items=items)


def get_moderation_post(db: Session, *, post_id: UUID) -> ModerationPostDetail:
    result = (
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
        .filter(Post.id == post_id)
        .group_by(Post.id, User.id)
        .first()
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    post, author, likes, dislikes, comments = result
    summary = _summarize_post(post, author, int(likes or 0), int(dislikes or 0), int(comments or 0))
    return ModerationPostDetail(**summary.model_dump(), avatar_url=author.avatar_url)


def list_moderation_media_assets(
    db: Session,
    *,
    skip: int | None = None,
    limit: int | None = None,
    user_id: UUID | None = None,
    search: str | None = None,
) -> ModerationMediaList:
    safe_skip, safe_limit = _normalize_pagination(skip, limit)
    filters = []
    if user_id is not None:
        filters.append(MediaAsset.user_id == user_id)
    media_filter = _pagination_filter_from_search(MediaAsset, search)
    if media_filter is not None:
        filters.append(media_filter)

    count_query = db.query(func.count(MediaAsset.id)).outerjoin(User, MediaAsset.user_id == User.id)
    for condition in filters:
        count_query = count_query.filter(condition)
    total = int(count_query.scalar() or 0)

    statement = (
        db.query(
            MediaAsset,
            User.username,
            User.display_name,
            User.role,
            User.avatar_url,
            func.count(func.distinct(MediaLike.id)).label("like_count"),
            func.count(func.distinct(MediaDislike.id)).label("dislike_count"),
            func.count(func.distinct(MediaComment.id)).label("comment_count"),
        )
        .outerjoin(User, MediaAsset.user_id == User.id)
        .outerjoin(MediaLike, MediaLike.media_asset_id == MediaAsset.id)
        .outerjoin(MediaDislike, MediaDislike.media_asset_id == MediaAsset.id)
        .outerjoin(MediaComment, MediaComment.media_asset_id == MediaAsset.id)
        .group_by(MediaAsset.id, User.id)
    )
    for condition in filters:
        statement = statement.filter(condition)

    rows = statement.order_by(MediaAsset.created_at.desc()).offset(safe_skip).limit(safe_limit).all()
    items = [
        _summarize_media_asset(asset, username, display_name, role, avatar_url, likes, dislikes, comments)
        for asset, username, display_name, role, avatar_url, likes, dislikes, comments in rows
    ]
    return ModerationMediaList(total=total, items=items)


def get_moderation_media_asset(db: Session, *, asset_id: UUID) -> ModerationMediaDetail:
    result = (
        db.query(
            MediaAsset,
            User.username,
            User.display_name,
            User.role,
            User.avatar_url,
            func.count(func.distinct(MediaLike.id)).label("like_count"),
            func.count(func.distinct(MediaDislike.id)).label("dislike_count"),
            func.count(func.distinct(MediaComment.id)).label("comment_count"),
        )
        .outerjoin(User, MediaAsset.user_id == User.id)
        .outerjoin(MediaLike, MediaLike.media_asset_id == MediaAsset.id)
        .outerjoin(MediaDislike, MediaDislike.media_asset_id == MediaAsset.id)
        .outerjoin(MediaComment, MediaComment.media_asset_id == MediaAsset.id)
        .filter(MediaAsset.id == asset_id)
        .group_by(MediaAsset.id, User.id)
        .first()
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")
    asset, username, display_name, role, avatar_url, likes, dislikes, comments = result
    summary = _summarize_media_asset(asset, username, display_name, role, avatar_url, likes, dislikes, comments)
    return ModerationMediaDetail(**summary.model_dump())


def _summarize_user(user: User, post_count: int, *, media_count: int = 0) -> ModerationUserSummary:
    user_id = cast(UUID, user.id)
    username = cast(str, user.username)
    display_name = cast(str | None, user.display_name)
    email = cast(str | None, user.email)
    role = cast(str | None, user.role)
    avatar_url = cast(str | None, user.avatar_url)
    created_at = cast(datetime, user.created_at)
    last_active = cast(datetime | None, user.last_active_at)
    return ModerationUserSummary(
        id=user_id,
        username=username,
        display_name=display_name,
        email=email,
        role=role,
        avatar_url=avatar_url,
        post_count=post_count,
        media_count=media_count,
        created_at=created_at,
        last_active_at=last_active,
        email_verified=bool(user.email_verified_at),
    )


def _summarize_post(
    post: Post,
    author: User,
    like_count: int,
    dislike_count: int,
    comment_count: int,
) -> ModerationPostSummary:
    post_id = cast(UUID, post.id)
    caption = cast(str, post.caption)
    created_at = cast(datetime, post.created_at)
    post_user_id = cast(UUID, post.user_id)
    username = cast(str, author.username)
    display_name = cast(str | None, author.display_name)
    role = cast(str | None, author.role)
    media_asset_id = cast(UUID | None, post.media_asset_id)
    media_url = cast(str | None, post.media_url)
    return ModerationPostSummary(
        id=post_id,
        caption=caption,
        created_at=created_at,
        user_id=post_user_id,
        username=username,
        display_name=display_name,
        role=role,
        media_asset_id=media_asset_id,
        media_url=media_url,
        like_count=like_count,
        dislike_count=dislike_count,
        comment_count=comment_count,
    )


def _summarize_media_asset(
    asset: MediaAsset,
    username: str | None,
    display_name: str | None,
    role: str | None,
    avatar_url: str | None,
    like_count: int,
    dislike_count: int,
    comment_count: int,
) -> ModerationMediaSummary:
    asset_id = cast(UUID, asset.id)
    owner_id = cast(UUID | None, asset.user_id)
    url = cast(str, asset.url)
    key = cast(str, asset.key)
    bucket = cast(str, asset.bucket)
    folder = cast(str | None, asset.folder)
    content_type = cast(str | None, asset.content_type)
    created_at = cast(datetime, asset.created_at)
    return ModerationMediaSummary(
        id=asset_id,
        user_id=owner_id,
        username=username,
        display_name=display_name,
        role=role,
        avatar_url=avatar_url,
        url=url,
        key=key,
        bucket=bucket,
        folder=folder,
        content_type=content_type,
        created_at=created_at,
        like_count=like_count,
        dislike_count=dislike_count,
        comment_count=comment_count,
    )


__all__ = [
    "load_moderation_dashboard",
    "list_moderation_users",
    "get_moderation_user",
    "update_user_role",
    "update_moderation_user",
    "delete_moderation_user",
    "list_moderation_posts",
    "get_moderation_post",
    "list_moderation_media_assets",
    "get_moderation_media_asset",
]
