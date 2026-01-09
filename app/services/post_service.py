"""Business logic for working with posts stored in PostgreSQL."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import Follow, MediaAsset, Post, PostComment, PostDislike, PostLike, User
from .translation_service import SupportedLang, translate_batch, translate_text
from .notification_service import NotificationType, add_notification
from .media_crypto import protect_media_value, reveal_media_value
from .media_service import delete_media_asset
from .spaces_service import SpacesConfigurationError, SpacesUploadError, upload_file_to_spaces
from .safety import enforce_safe_text


logger = logging.getLogger(__name__)


_HASHTAG_RE = re.compile(r"(?<!\w)#([a-zA-Z0-9_]{1,60})")


def _extract_hashtags(text: str) -> set[str]:
    if not text:
        return set()
    matches = _HASHTAG_RE.findall(text)
    return {match.strip().lower() for match in matches if match and match.strip()}


def list_trending_hashtags(
    db: Session,
    *,
    limit: int = 5,
    window_days: int = 30,
    sample_size: int = 750,
) -> list[dict[str, Any]]:
    """Return the most-used hashtags in recent posts.

    This is intentionally lightweight and database-agnostic: we pull recent captions
    and count hashtag usage in Python. Each hashtag is counted at most once per post.
    """

    resolved_limit = max(1, min(int(limit) if limit else 5, 20))
    resolved_window = max(1, min(int(window_days) if window_days else 30, 365))
    resolved_sample = max(resolved_limit * 10, min(int(sample_size) if sample_size else 750, 3000))

    cutoff = datetime.now(timezone.utc) - timedelta(days=resolved_window)

    stmt = (
        select(Post.caption)
        .where(Post.created_at >= cutoff)
        .order_by(Post.created_at.desc())
        .limit(resolved_sample)
    )
    rows = db.execute(stmt).all()
    counts: dict[str, int] = {}
    for (caption,) in rows:
        for tag in _extract_hashtags(cast(str | None, caption) or ""):
            counts[tag] = counts.get(tag, 0) + 1

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{"tag": tag, "count": count} for tag, count in ranked[:resolved_limit]]


def _normalize_avatar_url(raw: str | None) -> str | None:
    url = reveal_media_value(cast(str | None, raw))
    if not url:
        return None
    trimmed = url.strip()
    return trimmed or None


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
    url = reveal_media_value(cast(str | None, asset.url))
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

    normalized_caption = (caption or "").strip()
    if normalized_caption:
        enforce_safe_text(normalized_caption, field_name="caption")

    post = Post(
        user_id=user_id,
        caption=normalized_caption,
        media_url=protect_media_value(media_url),
        media_asset_id=normalized_asset_id,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    actor_name = str(getattr(user, "username", "") or "user")
    _notify_mentions(db, actor_id=user_id, actor_name=actor_name, post_id=cast(UUID, post.id), text=normalized_caption)
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
    post_owner_id = cast(UUID, post.user_id)
    if post_owner_id != requester_id and not can_edit_any:
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
        enforce_safe_text(text, field_name="caption")
        current_caption = cast(str | None, post.caption)
        if text != current_caption:
            setattr(post, "caption", text)
            changed = True

    next_asset_id = cast(UUID | None, post.media_asset_id)
    next_media_url = reveal_media_value(cast(str | None, post.media_url))

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

    setattr(post, "media_asset_id", next_asset_id)
    setattr(post, "media_url", protect_media_value(next_media_url))

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
    hashtag: str | None = None,
    target_language: SupportedLang | None = None,
) -> list[dict[str, Any]]:
    """Return posts ordered by personalised priority, optionally filtered by author."""

    base_columns = [
        Post,
        User.username.label("username"),
        User.avatar_url.label("avatar_url"),
        User.role.label("author_role"),
        MediaAsset.content_type.label("media_content_type"),
        MediaAsset.url.label("media_asset_url"),
    ]
    statement = (
        select(*base_columns)
        .join(User, Post.user_id == User.id)
        .outerjoin(MediaAsset, Post.media_asset_id == MediaAsset.id)
    )

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

    if hashtag:
        normalized_tag = hashtag.strip().lstrip('#').lower()
        if normalized_tag:
            pattern = f"%#{normalized_tag}%"
            statement = statement.where(func.lower(Post.caption).like(pattern))

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
        media_content_type_value = row[idx]
        idx += 1
        media_asset_url_value = row[idx]
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
        avatar_url = _normalize_avatar_url(cast(str | None, avatar_value))
        post_media_url_value = reveal_media_value(cast(str | None, post.media_url))
        asset_media_url_plain = reveal_media_value(cast(str | None, media_asset_url_value))
        # Media validation is handled asynchronously by the cleanup task to keep feed requests fast.
        record_media_url = post_media_url_value or asset_media_url_plain
        media_content_type = cast(str | None, media_content_type_value)

        record: dict[str, Any] = {
            "id": post.id,
            "user_id": post.user_id,
            "caption": post.caption,
            "media_url": record_media_url,
            "media_asset_id": post.media_asset_id,
            "created_at": post.created_at,
            "username": username,
            "avatar_url": avatar_url,
            "author_role": cast(str | None, role_value),
            "media_content_type": media_content_type,
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

    if target_language is not None and records:
        captions = [record.get("caption") or "" for record in records]
        translations = translate_batch(captions, target_language)
        for record, translated_caption in zip(records, translations):
            record["translated_caption"] = translated_caption
            record["translation_language"] = target_language

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


def get_post_engagement_snapshot(
    db: Session,
    *,
    post_id: UUID,
    viewer_id: UUID | None = None,
) -> dict[str, Any]:
    """Return engagement totals plus viewer flags for a post."""

    _get_post_or_404(db, post_id)
    return _post_engagement_snapshot(db, post_id, viewer_id)


def set_post_like_state(
    db: Session,
    *,
    post_id: UUID,
    user_id: UUID,
    should_like: bool,
) -> dict[str, Any]:
    post = _get_post_or_404(db, post_id)
    liker = db.get(User, user_id)
    if liker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    post_author_id = cast(UUID, post.user_id)

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

    snapshot = _post_engagement_snapshot(db, post_id, user_id)

    if should_like and existing is None and post_author_id != user_id:
        liker_name = liker.username or "A user"
        payload = {"post_id": str(post_id)}
        try:
            add_notification(
                db,
                recipient_id=post_author_id,
                sender_id=user_id,
                content=f"@{liker_name} liked your post.",
                type_=NotificationType.POST_LIKE,
                payload=payload,
            )
        except Exception:
            logger.warning("Failed to enqueue like notification for post %s", post_id)

    return snapshot


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


def list_post_comments(db: Session, *, post_id: UUID, target_language: SupportedLang | None = None) -> list[dict[str, Any]]:
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
        parent_id_value = cast(UUID | None, comment.parent_id)
        node = {
            "id": comment.id,
            "post_id": comment.post_id,
            "user_id": comment.user_id,
            "username": cast(str | None, username),
            "avatar_url": _normalize_avatar_url(cast(str | None, avatar_url)),
            "role": cast(str | None, role),
            "content": comment.content,
            "parent_id": parent_id_value,
            "created_at": comment.created_at,
            "replies": [],
        }
        nodes[comment.id] = node
        if parent_id_value is not None and parent_id_value in nodes:
            nodes[parent_id_value]["replies"].append(node)
        else:
            roots.append(node)

    if target_language is not None:
        for root in roots:
            _apply_comment_translation(root, target_language)

    return roots


def _serialize_comment(comment: PostComment, user: User) -> dict[str, Any]:
    parent_value = cast(UUID | None, comment.parent_id)
    return {
        "id": comment.id,
        "post_id": comment.post_id,
        "user_id": user.id,
        "username": user.username,
        "avatar_url": _normalize_avatar_url(cast(str | None, user.avatar_url)),
        "role": getattr(user, "role", None),
        "content": comment.content,
        "parent_id": parent_value,
        "created_at": comment.created_at,
        "replies": [],
    }


def _apply_comment_translation(comment: dict[str, Any], target_language: SupportedLang) -> None:
    comment["translated_content"] = translate_text(comment.get("content") or "", target_language)
    comment["translation_language"] = target_language
    for reply in comment.get("replies") or []:
        _apply_comment_translation(reply, target_language)


def _extract_mentioned_user_ids(
    db: Session,
    text: str | None,
    *,
    exclude_ids: set[UUID] | None = None,
    limit: int = 10,
) -> set[UUID]:
    value = (text or "").strip()
    if not value:
        return set()
    matches = re.findall(r"@([A-Za-z0-9_\.]{2,32})", value)
    if not matches:
        return set()
    usernames = {token.lower() for token in matches}
    if not usernames:
        return set()
    stmt = select(User.id).where(func.lower(User.username).in_(usernames)).limit(max(limit, 1))
    rows = db.execute(stmt).scalars().all()
    found_ids: set[UUID] = set(cast(UUID, row) for row in rows)
    if exclude_ids:
        found_ids.difference_update(exclude_ids)
    return found_ids


def _notify_mentions(
    db: Session,
    *,
    actor_id: UUID,
    actor_name: str,
    post_id: UUID,
    text: str | None,
    comment_id: UUID | None = None,
) -> None:
    try:
        mention_ids = _extract_mentioned_user_ids(db, text, exclude_ids={actor_id})
    except Exception:
        logger.warning("Failed to parse mentions", exc_info=True)
        return
    if not mention_ids:
        return
    payload: dict[str, Any] = {"post_id": str(post_id)}
    if comment_id is not None:
        payload["comment_id"] = str(comment_id)
    for recipient_id in mention_ids:
        try:
            add_notification(
                db,
                recipient_id=recipient_id,
                sender_id=actor_id,
                content=f"@{actor_name} mentioned you.",
                type_=NotificationType.MENTION,
                payload=payload,
            )
        except Exception:
            logger.warning("Failed to enqueue mention notification", exc_info=True)


def create_post_comment(
    db: Session,
    *,
    post_id: UUID,
    author: User,
    content: str,
    parent_id: UUID | None = None,
    target_language: SupportedLang | None = None,
) -> dict[str, Any]:
    post = _get_post_or_404(db, post_id)
    text = (content or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Comment cannot be empty")
    enforce_safe_text(text, field_name="comment")

    parent: PostComment | None = None
    if parent_id is not None:
        parent = db.get(PostComment, parent_id)
        parent_post_id = cast(UUID | None, parent.post_id) if parent is not None else None
        if parent is None or parent_post_id != post_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid parent comment")

    comment = PostComment(post_id=post.id, user_id=author.id, content=text, parent_id=parent.id if parent else None)
    db.add(comment)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add comment") from exc

    db.refresh(comment)

    commenter_id = cast(UUID, author.id)
    post_author_id = cast(UUID, post.user_id)
    base_payload = {"post_id": str(post.id), "comment_id": str(comment.id)}
    notified: set[str] = set()

    def _enqueue_notification(recipient_id: UUID, type_: NotificationType, content: str, payload: dict[str, Any]) -> None:
        if recipient_id == commenter_id:
            return
        key = str(recipient_id)
        if key in notified:
            return
        notified.add(key)
        try:
            add_notification(
                db,
                recipient_id=recipient_id,
                sender_id=commenter_id,
                content=content,
                type_=type_,
                payload=payload,
            )
        except Exception:
            logger.warning("Failed to enqueue comment notification for post %s", post.id)

    commenter_name = str(getattr(author, "username", "") or "A user")
    if post_author_id != commenter_id:
        _enqueue_notification(
            post_author_id,
            NotificationType.POST_COMMENT,
            f"@{commenter_name} commented on your post.",
            base_payload,
        )

    if parent is not None:
        parent_author_id = cast(UUID | None, parent.user_id)
        if parent_author_id is not None and parent_author_id not in {commenter_id, post_author_id}:
            reply_payload = {**base_payload, "parent_comment_id": str(parent.id)}
            _enqueue_notification(
                parent_author_id,
                NotificationType.POST_COMMENT_REPLY,
                f"@{commenter_name} replied to your comment.",
                reply_payload,
            )

    _notify_mentions(
        db,
        actor_id=commenter_id,
        actor_name=commenter_name,
        post_id=cast(UUID, post.id),
        text=text,
        comment_id=cast(UUID, comment.id),
    )

    payload = _serialize_comment(comment, author)
    if target_language is not None:
        _apply_comment_translation(payload, target_language)
    return payload


def _get_comment_or_404(db: Session, comment_id: UUID) -> PostComment:
    comment = db.get(PostComment, comment_id)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return comment


def update_post_comment(
    db: Session,
    *,
    comment_id: UUID,
    requester_id: UUID,
    requester_role: str | None,
    content: str,
    target_language: SupportedLang | None = None,
) -> dict[str, Any]:
    comment = _get_comment_or_404(db, comment_id)
    user = db.get(User, comment.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment author not found")

    normalized_role = (requester_role or "").lower()
    can_edit_any = normalized_role in {"owner", "admin"}
    comment_author_id = cast(UUID, comment.user_id)
    if comment_author_id != requester_id and not can_edit_any:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to edit this comment")

    text = (content or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Comment cannot be empty")
    enforce_safe_text(text, field_name="comment")

    if text == comment.content:
        payload = _serialize_comment(comment, user)
        if target_language is not None:
            _apply_comment_translation(payload, target_language)
        return payload

    setattr(comment, "content", text)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update comment") from exc

    db.refresh(comment)
    payload = _serialize_comment(comment, user)
    if target_language is not None:
        _apply_comment_translation(payload, target_language)
    return payload


def delete_post_comment(
    db: Session,
    *,
    comment_id: UUID,
    requester_id: UUID,
    requester_role: str | None,
) -> UUID:
    comment = _get_comment_or_404(db, comment_id)
    normalized_role = (requester_role or "").lower()
    can_delete_any = normalized_role in {"owner", "admin"}
    comment_author_id = cast(UUID, comment.user_id)
    if comment_author_id != requester_id and not can_delete_any:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete this comment")

    post_id = cast(UUID, comment.post_id)
    try:
        db.delete(comment)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete comment") from exc

    return post_id


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
    asset_id = cast(UUID | None, post.media_asset_id)
    db.delete(post)
    db.commit()

    if delete_media and asset_id is not None:
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
    "update_post_comment",
    "delete_post_comment",
    "delete_post_record",
    "delete_old_posts",
    "update_post_record",
    "get_post_engagement_snapshot",
]
