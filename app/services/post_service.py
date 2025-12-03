"""Business logic for working with posts stored in PostgreSQL."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import Follow, MediaAsset, Post, PostComment, PostDislike, PostLike, User
from .media_service import delete_media_asset
from .spaces_service import SpacesConfigurationError, SpacesUploadError, upload_file_to_spaces


def _normalize_media_asset_id(candidate: UUID | str | None) -> UUID | None:
    if isinstance(candidate, UUID):
        return candidate
    if isinstance(candidate, str):
        stripped = candidate.strip()
        if not stripped:
            return None
        try:
            return UUID(stripped)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="media_asset_id must be a valid UUID",
            ) from exc
    return None


def _resolve_media_asset_url(db: Session, asset_id: UUID) -> str:
    asset = db.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")
    url = cast(str | None, asset.url)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Media asset is missing a URL",
        )
    return url


async def _upload_post_media(
    file: UploadFile,
    *,
    db: Session,
    user_id: UUID,
) -> tuple[UUID, str]:
    try:
        upload_result = await upload_file_to_spaces(file, folder="posts", db=db, user_id=user_id)
    except SpacesConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except SpacesUploadError as exc:  # pragma: no cover - network bound
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    if (
        not upload_result.key
        or not upload_result.key.strip()
        or not upload_result.url
        or not upload_result.url.strip()
        or not upload_result.bucket
        or not upload_result.bucket.strip()
        or not upload_result.content_type
        or not upload_result.content_type.strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid media metadata returned from Spaces",
        )

    asset_id = upload_result.asset_id
    if asset_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist media metadata",
        )

    return asset_id, upload_result.url


async def create_post_record(
    db: Session,
    *,
    user_id: UUID,
    caption: str,
    media_asset_id: UUID | str | None = None,
    file: UploadFile | None = None,
) -> Post:
    """Create and persist a new post for the given user."""



    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    normalized_asset_id = _normalize_media_asset_id(media_asset_id)

    if file is not None and normalized_asset_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a file upload or a media_asset_id, not both",
        )

    media_url: str | None = None
    if file is not None:
        normalized_asset_id, media_url = await _upload_post_media(file, db=db, user_id=user_id)

    if normalized_asset_id is not None and file is None:
        media_url = _resolve_media_asset_url(db, normalized_asset_id)

    post = Post(user_id=user_id, caption=caption, media_url=media_url, media_asset_id=normalized_asset_id)
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


async def update_post_record(
    db: Session,
    *,
    post_id: UUID,
    requester_id: UUID,
    requester_role: str | None = None,
    caption: str | None = None,
    media_asset_id: UUID | str | None = None,
    file: UploadFile | None = None,
    remove_media: bool = False,
) -> Post:
    post = _get_post_or_404(db, post_id)
    normalized_role = (requester_role or "").lower()
    can_edit_any = normalized_role in {"owner", "admin"}
    if post.user_id != requester_id and not can_edit_any:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to edit this post")

    normalized_asset_id = _normalize_media_asset_id(media_asset_id)

    if file is not None and normalized_asset_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a file upload or a media_asset_id, not both",
        )

    if remove_media and (file is not None or normalized_asset_id is not None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Remove media or supply new media, not both",
        )

    changed = False
    if caption is not None:
        text = caption.strip()
        if not text:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Caption cannot be empty")
        if text != post.caption:
            post.caption = text
            changed = True

    next_asset_id = post.media_asset_id
    next_media_url = post.media_url

    if remove_media:
        if next_asset_id is not None or next_media_url is not None:
            next_asset_id = None
            next_media_url = None
            changed = True
    elif file is not None:
        next_asset_id, next_media_url = await _upload_post_media(file, db=db, user_id=requester_id)
        changed = True
    elif normalized_asset_id is not None:
        resolved_url = _resolve_media_asset_url(db, normalized_asset_id)
        if normalized_asset_id != next_asset_id or resolved_url != next_media_url:
            next_asset_id = normalized_asset_id
            next_media_url = resolved_url
            changed = True

    if not changed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No changes detected")

    post.media_asset_id = next_asset_id
    post.media_url = next_media_url

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update post") from exc

    db.refresh(post)
    return post




def list_feed_records(
    db: Session,
    *,
    viewer_id: UUID | None = None,
    author_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Return posts ordered by personalised priority, optionally filtered by author."""

    base_columns = [
        Post,
        User.username.label("username"),
        User.avatar_url.label("avatar_url"),
        User.role.label("author_role"),
    ]
    statement = select(*base_columns).join(User, Post.user_id == User.id)

    like_count_subquery = (
        select(func.count(PostLike.id)).where(PostLike.post_id == Post.id).scalar_subquery()
    )
    dislike_count_subquery = (
        select(func.count(PostDislike.id)).where(PostDislike.post_id == Post.id).scalar_subquery()
    )
    comment_count_subquery = (
        select(func.count(PostComment.id)).where(PostComment.post_id == Post.id).scalar_subquery()
    )

    statement = statement.add_columns(like_count_subquery, dislike_count_subquery, comment_count_subquery)
    if author_id is not None:
        statement = statement.where(Post.user_id == author_id)

    include_follow_weight = viewer_id is not None
    follow_match_col = None
    follow_priority_col = None
    viewer_like_col = None
    viewer_dislike_col = None

    if viewer_id is not None:
        viewer_like_col = (
            select(func.count(PostLike.id))
            .where(PostLike.post_id == Post.id, PostLike.user_id == viewer_id)
            .scalar_subquery()
        )
        viewer_dislike_col = (
            select(func.count(PostDislike.id))
            .where(PostDislike.post_id == Post.id, PostDislike.user_id == viewer_id)
            .scalar_subquery()
        )
        statement = statement.add_columns(viewer_like_col, viewer_dislike_col)

    if include_follow_weight and viewer_id is not None:
        follow_subquery = (
            select(Follow.following_id.label("following_id"))
            .where(Follow.follower_id == viewer_id)
            .subquery()
        )
        follow_match_col = case((follow_subquery.c.following_id.isnot(None), 1), else_=0).label("follow_match")
        self_match_col = case((Post.user_id == viewer_id, 1), else_=0)
        follow_priority_col = (self_match_col * 2 + follow_match_col).label("follow_priority")
        statement = (
            statement.add_columns(follow_match_col, follow_priority_col)
            .outerjoin(follow_subquery, follow_subquery.c.following_id == Post.user_id)
        )

    statement = statement.order_by(Post.created_at.desc())

    records: list[dict[str, Any]] = []
    rows = db.execute(statement).all()
    for row in rows:
        idx = 0
        post = row[idx]
        idx += 1
        username_value = row[idx]
        idx += 1
        avatar_value = row[idx]
        idx += 1
        role_value = row[idx]
        idx += 1
        like_count_value = row[idx]
        idx += 1
        dislike_count_value = row[idx]
        idx += 1
        comment_count_value = row[idx]
        idx += 1
        viewer_like_value = None
        viewer_dislike_value = None
        if viewer_like_col is not None:
            viewer_like_value = row[idx]
            idx += 1
        if viewer_dislike_col is not None:
            viewer_dislike_value = row[idx]
            idx += 1
        follow_match_value = None
        follow_priority_value = None
        if include_follow_weight and follow_match_col is not None and follow_priority_col is not None:
            follow_match_value = row[idx]
            idx += 1
            follow_priority_value = row[idx]
            idx += 1

        username = cast(str | None, username_value)
        avatar_url = cast(str | None, avatar_value)
        record: dict[str, Any] = {
            "id": post.id,
            "user_id": post.user_id,
            "caption": post.caption,
            "media_url": post.media_url,
            "media_asset_id": post.media_asset_id,
            "created_at": post.created_at,
            "username": username,
            "avatar_url": avatar_url,
            "author_role": cast(str | None, role_value),
            "like_count": int(like_count_value or 0),
            "dislike_count": int(dislike_count_value or 0),
            "comment_count": int(comment_count_value or 0),
            "viewer_has_liked": bool(viewer_like_value) if viewer_like_col is not None else False,
            "viewer_has_disliked": bool(viewer_dislike_value) if viewer_dislike_col is not None else False,
        }

        if include_follow_weight:
            record["is_following_author"] = bool(follow_match_value)
            record["follow_priority"] = int(follow_priority_value or 0)

        records.append(record)

    return records


def _get_post_or_404(db: Session, post_id: UUID) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


def _post_engagement_snapshot(db: Session, post_id: UUID, viewer_id: UUID | None) -> dict[str, Any]:
    like_count = db.scalar(select(func.count(PostLike.id)).where(PostLike.post_id == post_id)) or 0
    dislike_count = db.scalar(select(func.count(PostDislike.id)).where(PostDislike.post_id == post_id)) or 0
    comment_count = db.scalar(select(func.count(PostComment.id)).where(PostComment.post_id == post_id)) or 0
    viewer_has_liked = False
    viewer_has_disliked = False
    if viewer_id is not None:
        viewer_has_liked = (
            db.scalar(
                select(PostLike.id).where(PostLike.post_id == post_id, PostLike.user_id == viewer_id).limit(1)
            )
            is not None
        )
        viewer_has_disliked = (
            db.scalar(
                select(PostDislike.id).where(PostDislike.post_id == post_id, PostDislike.user_id == viewer_id).limit(1)
            )
            is not None
        )
    return {
        "post_id": post_id,
        "like_count": int(like_count),
        "dislike_count": int(dislike_count),
        "comment_count": int(comment_count),
        "viewer_has_liked": viewer_has_liked,
        "viewer_has_disliked": viewer_has_disliked,
    }


def set_post_like_state(
    db: Session,
    *,
    post_id: UUID,
    user_id: UUID,
    should_like: bool,
) -> dict[str, Any]:
    _get_post_or_404(db, post_id)

    existing = db.scalar(select(PostLike).where(PostLike.post_id == post_id, PostLike.user_id == user_id))
    existing_dislike = db.scalar(
        select(PostDislike).where(PostDislike.post_id == post_id, PostDislike.user_id == user_id)
    )

    if should_like and existing is None:
        db.add(PostLike(post_id=post_id, user_id=user_id))
    elif not should_like and existing is not None:
        db.delete(existing)

    if should_like and existing_dislike is not None:
        db.delete(existing_dislike)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update like") from exc

    return _post_engagement_snapshot(db, post_id, user_id)


def set_post_dislike_state(
    db: Session,
    *,
    post_id: UUID,
    user_id: UUID,
    should_dislike: bool,
) -> dict[str, Any]:
    _get_post_or_404(db, post_id)

    existing = db.scalar(select(PostDislike).where(PostDislike.post_id == post_id, PostDislike.user_id == user_id))
    existing_like = db.scalar(select(PostLike).where(PostLike.post_id == post_id, PostLike.user_id == user_id))

    if should_dislike and existing is None:
        db.add(PostDislike(post_id=post_id, user_id=user_id))
    elif not should_dislike and existing is not None:
        db.delete(existing)

    if should_dislike and existing_like is not None:
        db.delete(existing_like)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update dislike") from exc

    return _post_engagement_snapshot(db, post_id, user_id)


def list_post_comments(db: Session, *, post_id: UUID) -> list[dict[str, Any]]:
    _get_post_or_404(db, post_id)
    stmt = (
        select(PostComment, User.username, User.avatar_url, User.role)
        .join(User, PostComment.user_id == User.id)
        .where(PostComment.post_id == post_id)
        .order_by(PostComment.created_at.asc())
    )
    rows = db.execute(stmt).all()

    nodes: dict[UUID, dict[str, Any]] = {}
    roots: list[dict[str, Any]] = []

    for comment, username, avatar_url, role in rows:
        node = {
            "id": comment.id,
            "post_id": comment.post_id,
            "user_id": comment.user_id,
            "username": cast(str | None, username),
            "avatar_url": cast(str | None, avatar_url),
            "role": cast(str | None, role),
            "content": comment.content,
            "parent_id": comment.parent_id,
            "created_at": comment.created_at,
            "replies": [],
        }
        nodes[comment.id] = node
        if comment.parent_id and comment.parent_id in nodes:
            nodes[comment.parent_id]["replies"].append(node)
        else:
            roots.append(node)

    return roots


def create_post_comment(
    db: Session,
    *,
    post_id: UUID,
    author: User,
    content: str,
    parent_id: UUID | None = None,
) -> dict[str, Any]:
    post = _get_post_or_404(db, post_id)
    text = (content or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Comment cannot be empty")

    parent: PostComment | None = None
    if parent_id is not None:
        parent = db.get(PostComment, parent_id)
        if parent is None or parent.post_id != post.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid parent comment")

    comment = PostComment(post_id=post.id, user_id=author.id, content=text, parent_id=parent.id if parent else None)
    db.add(comment)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add comment") from exc

    db.refresh(comment)
    return {
        "id": comment.id,
        "post_id": comment.post_id,
        "user_id": author.id,
        "username": author.username,
        "avatar_url": author.avatar_url,
        "role": getattr(author, "role", None),
        "content": comment.content,
        "parent_id": comment.parent_id,
        "created_at": comment.created_at,
        "replies": [],
    }


def delete_post_record(
    db: Session,
    *,
    post_id: UUID,
    requester_id: UUID,
    requester_role: str | None = None,
    delete_media: bool = True,
) -> None:
    """Delete a post when requester is author or privileged role."""

    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    post_author_id = cast(UUID, post.user_id)
    normalized_role = (requester_role or "").lower()
    can_delete_any = normalized_role in {"owner", "admin"}
    if post_author_id != requester_id and not can_delete_any:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete this post")
    asset_id = post.media_asset_id
    db.delete(post)
    db.commit()

    if delete_media and asset_id:
        try:
            delete_media_asset(db, asset_id=asset_id, delete_remote=True)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                return
            raise


def delete_old_posts(db: Session, *, older_than: timedelta | None = None) -> int:
    """Remove posts older than the supplied ``older_than`` delta (default 2 days)."""

    cutoff_delta = older_than or timedelta(days=2)
    cutoff = datetime.now(timezone.utc) - cutoff_delta
    stmt = delete(Post).where(Post.created_at < cutoff).returning(Post.id)
    try:
        result = db.execute(stmt)
        db.commit()
        return len(result.fetchall())
    except SQLAlchemyError:
        db.rollback()
        return 0


__all__ = [
    "create_post_record",
    "list_feed_records",
    "set_post_like_state",
    "set_post_dislike_state",
    "list_post_comments",
    "create_post_comment",
    "delete_post_record",
    "delete_old_posts",
    "update_post_record",
]
