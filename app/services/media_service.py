"""Media persistence and storage helpers for the social app."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Tuple, cast
from uuid import UUID, uuid4

import requests
from fastapi import HTTPException, UploadFile, status
from requests import RequestException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import MediaAsset, MediaComment, MediaDislike, MediaLike, Post, User
from ..security.data_vault import DataVaultError
from .media_crypto import reveal_media_value
from .spaces_service import SpacesDeletionError, delete_file_from_spaces


logger = logging.getLogger(__name__)


def _asset_public_url(asset: MediaAsset) -> str | None:
    raw_value = cast(str | None, getattr(asset, "url", None))
    try:
        return reveal_media_value(raw_value)
    except DataVaultError as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to decrypt media url for asset %s: %s", getattr(asset, "id", "?"), exc)
        return None


def _asset_storage_key(asset: MediaAsset) -> str | None:
    raw_value = cast(str | None, getattr(asset, "key", None))
    try:
        return reveal_media_value(raw_value)
    except DataVaultError as exc:  # pragma: no cover
        logger.warning("Unable to decrypt media key for asset %s: %s", getattr(asset, "id", "?"), exc)
        return None


def list_media_for_user(db: Session, user_id: UUID) -> list[MediaAsset]:
    """Return media assets uploaded by the specified user."""

    stmt = select(MediaAsset).where(MediaAsset.user_id == user_id).order_by(MediaAsset.created_at.desc())
    return list(db.scalars(stmt))


MAX_MEDIA_FEED_LIMIT = 50
PUBLIC_MEDIA_FOLDERS: tuple[str, ...] = ("media", "posts")


def media_url_is_fetchable(url: str | None, *, timeout: float = 3.0) -> bool:
    """Return True when the provided URL responds successfully."""

    candidate = (url or "").strip()
    if not candidate:
        return False

    def _probe(method):
        try:
            resp = method(candidate, allow_redirects=True, timeout=timeout, stream=True)
        except RequestException as exc:  # pragma: no cover - network
            logger.warning("%s probe failed for url %s: %s", method.__name__.upper(), candidate, exc)
            return None
        status_code = getattr(resp, "status_code", 500)
        resp.close()
        return status_code

    status_code = _probe(requests.head)
    if status_code is None:
        return False
    if status_code >= 400 or status_code == 405:
        status_code = _probe(requests.get)
        if status_code is None:
            return False
    return status_code < 400


def _media_asset_is_fetchable(asset: MediaAsset, *, timeout: float = 3.0) -> bool:
    """Return True when the stored media URL responds successfully."""

    if asset is None:
        return False
    url = _asset_public_url(asset)
    if not url:
        return False
    return media_url_is_fetchable(url, timeout=timeout)


def _detach_posts_for_assets(db: Session, asset_ids: list[UUID]) -> None:
    """Clear media references from posts linked to the provided asset IDs."""

    if not asset_ids:
        return

    posts = db.query(Post).where(Post.media_asset_id.in_(asset_ids)).all()
    for post in posts:
        post.media_asset_id = None
        post.media_url = None


def _delete_media_asset_objects(
    db: Session,
    assets: Iterable[MediaAsset],
    *,
    delete_remote: bool,
    fail_on_remote_error: bool = True,
) -> int:
    """Delete ``MediaAsset`` rows plus their remote files when requested."""

    asset_list = [asset for asset in assets if asset is not None]
    if not asset_list:
        return 0

    if delete_remote:
        for asset in asset_list:
            key = (_asset_storage_key(asset) or "").strip()
            if not key:
                continue
            try:
                delete_file_from_spaces(key)
            except SpacesDeletionError as exc:
                if fail_on_remote_error:
                    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
                logger.warning("Unable to delete remote media asset %s: %s", asset.id, exc)

    asset_ids = [asset.id for asset in asset_list]
    _detach_posts_for_assets(db, asset_ids)

    for asset in asset_list:
        db.delete(asset)

    return len(asset_list)


def _purge_missing_media_assets(db: Session, asset_ids: list[UUID]) -> None:
    if not asset_ids:
        return
    assets = db.query(MediaAsset).filter(MediaAsset.id.in_(asset_ids)).all()
    if not assets:
        return
    try:
        removed = _delete_media_asset_objects(
            db,
            assets,
            delete_remote=True,
            fail_on_remote_error=False,
        )
        db.commit()
        if removed:
            logger.info("Purged %d missing media assets from feed", removed)
    except SQLAlchemyError:
        db.rollback()
        raise


def list_media_feed(db: Session, *, viewer_id: UUID | None = None, limit: int = 25) -> list[dict[str, Any]]:
    """Return a chronological media reel enriched with engagement metadata."""

    clamped_limit = max(1, min(limit, MAX_MEDIA_FEED_LIMIT))

    like_count_subquery = (
        select(func.count(MediaLike.id)).where(MediaLike.media_asset_id == MediaAsset.id).scalar_subquery()
    )
    dislike_count_subquery = (
        select(func.count(MediaDislike.id)).where(MediaDislike.media_asset_id == MediaAsset.id).scalar_subquery()
    )
    comment_count_subquery = (
        select(func.count(MediaComment.id)).where(MediaComment.media_asset_id == MediaAsset.id).scalar_subquery()
    )

    columns = [
        MediaAsset,
        User.username.label("username"),
        User.display_name.label("display_name"),
        User.avatar_url.label("avatar_url"),
        User.role.label("role"),
        like_count_subquery,
        dislike_count_subquery,
        comment_count_subquery,
    ]

    viewer_like_col = None
    viewer_dislike_col = None
    if viewer_id is not None:
        viewer_like_col = (
            select(func.count(MediaLike.id))
            .where(MediaLike.media_asset_id == MediaAsset.id, MediaLike.user_id == viewer_id)
            .scalar_subquery()
        )
        viewer_dislike_col = (
            select(func.count(MediaDislike.id))
            .where(MediaDislike.media_asset_id == MediaAsset.id, MediaDislike.user_id == viewer_id)
            .scalar_subquery()
        )
        columns.extend([viewer_like_col, viewer_dislike_col])

    statement = (
        select(*columns)
        .outerjoin(User, MediaAsset.user_id == User.id)
        .order_by(MediaAsset.created_at.desc())
        .limit(clamped_limit)
    )

    if PUBLIC_MEDIA_FOLDERS:
        statement = statement.where(
            or_(
                MediaAsset.folder.is_(None),
                MediaAsset.folder.in_(PUBLIC_MEDIA_FOLDERS),
            )
        )

    rows = db.execute(statement).all()
    invalid_asset_ids: list[UUID] = []
    filtered_rows = []
    for row in rows:
        idx = 0
        asset = row[idx]
        idx += 1
        if asset is None:
            continue
        if not _media_asset_is_fetchable(asset):
            invalid_asset_ids.append(asset.id)
            continue
        filtered_rows.append(row)

    if invalid_asset_ids:
        try:
            _purge_missing_media_assets(db, invalid_asset_ids)
        except SQLAlchemyError:
            db.rollback()
            raise

    records: list[dict[str, Any]] = []
    for row in filtered_rows:
        idx = 0
        asset = row[idx]
        idx += 1
        username_value = row[idx]
        idx += 1
        display_name_value = row[idx]
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

        record: dict[str, Any] = {
            "id": asset.id,
            "user_id": asset.user_id,
            "username": cast(str | None, username_value),
            "display_name": cast(str | None, display_name_value),
            "avatar_url": cast(str | None, avatar_value),
            "role": cast(str | None, role_value),
            "url": _asset_public_url(asset) or "",
            "content_type": asset.content_type,
            "created_at": asset.created_at,
            "like_count": int(like_count_value or 0),
            "dislike_count": int(dislike_count_value or 0),
            "comment_count": int(comment_count_value or 0),
            "viewer_has_liked": bool(viewer_like_value) if viewer_like_col is not None else False,
            "viewer_has_disliked": bool(viewer_dislike_value) if viewer_dislike_col is not None else False,
        }

        records.append(record)

    return records


def _get_media_asset_or_404(db: Session, asset_id: UUID) -> MediaAsset:
    asset = db.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")
    return asset


def _media_engagement_snapshot(db: Session, asset_id: UUID, viewer_id: UUID | None) -> dict[str, Any]:
    like_count = db.scalar(select(func.count(MediaLike.id)).where(MediaLike.media_asset_id == asset_id)) or 0
    dislike_count = db.scalar(select(func.count(MediaDislike.id)).where(MediaDislike.media_asset_id == asset_id)) or 0
    comment_count = db.scalar(select(func.count(MediaComment.id)).where(MediaComment.media_asset_id == asset_id)) or 0
    viewer_has_liked = False
    viewer_has_disliked = False
    if viewer_id is not None:
        viewer_has_liked = (
            db.scalar(
                select(MediaLike.id)
                .where(MediaLike.media_asset_id == asset_id, MediaLike.user_id == viewer_id)
                .limit(1)
            )
            is not None
        )
        viewer_has_disliked = (
            db.scalar(
                select(MediaDislike.id)
                .where(MediaDislike.media_asset_id == asset_id, MediaDislike.user_id == viewer_id)
                .limit(1)
            )
            is not None
        )
    return {
        "media_asset_id": asset_id,
        "like_count": int(like_count),
        "dislike_count": int(dislike_count),
        "comment_count": int(comment_count),
        "viewer_has_liked": viewer_has_liked,
        "viewer_has_disliked": viewer_has_disliked,
    }


def set_media_like_state(
    db: Session,
    *,
    media_asset_id: UUID,
    user_id: UUID,
    should_like: bool,
) -> dict[str, Any]:
    _get_media_asset_or_404(db, media_asset_id)

    existing_like = db.scalar(
        select(MediaLike).where(MediaLike.media_asset_id == media_asset_id, MediaLike.user_id == user_id)
    )
    existing_dislike = db.scalar(
        select(MediaDislike).where(MediaDislike.media_asset_id == media_asset_id, MediaDislike.user_id == user_id)
    )

    if should_like and existing_like is None:
        db.add(MediaLike(media_asset_id=media_asset_id, user_id=user_id))
    elif not should_like and existing_like is not None:
        db.delete(existing_like)

    if should_like and existing_dislike is not None:
        db.delete(existing_dislike)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update like") from exc

    return _media_engagement_snapshot(db, media_asset_id, user_id)


def set_media_dislike_state(
    db: Session,
    *,
    media_asset_id: UUID,
    user_id: UUID,
    should_dislike: bool,
) -> dict[str, Any]:
    _get_media_asset_or_404(db, media_asset_id)

    existing_dislike = db.scalar(
        select(MediaDislike).where(MediaDislike.media_asset_id == media_asset_id, MediaDislike.user_id == user_id)
    )
    existing_like = db.scalar(
        select(MediaLike).where(MediaLike.media_asset_id == media_asset_id, MediaLike.user_id == user_id)
    )

    if should_dislike and existing_dislike is None:
        db.add(MediaDislike(media_asset_id=media_asset_id, user_id=user_id))
    elif not should_dislike and existing_dislike is not None:
        db.delete(existing_dislike)

    if should_dislike and existing_like is not None:
        db.delete(existing_like)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update dislike") from exc

    return _media_engagement_snapshot(db, media_asset_id, user_id)


def list_media_comments(db: Session, *, media_asset_id: UUID) -> list[dict[str, Any]]:
    _get_media_asset_or_404(db, media_asset_id)
    stmt = (
        select(MediaComment, User.username, User.avatar_url, User.role)
        .join(User, MediaComment.user_id == User.id)
        .where(MediaComment.media_asset_id == media_asset_id)
        .order_by(MediaComment.created_at.asc())
    )
    rows = db.execute(stmt).all()

    nodes: dict[UUID, dict[str, Any]] = {}
    roots: list[dict[str, Any]] = []

    for comment, username, avatar_url, role in rows:
        node = {
            "id": comment.id,
            "media_asset_id": comment.media_asset_id,
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


def create_media_comment(
    db: Session,
    *,
    media_asset_id: UUID,
    author: User,
    content: str,
    parent_id: UUID | None = None,
) -> dict[str, Any]:
    _get_media_asset_or_404(db, media_asset_id)
    text = (content or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Comment cannot be empty")

    parent: MediaComment | None = None
    if parent_id is not None:
        parent = db.get(MediaComment, parent_id)
        if parent is None or parent.media_asset_id != media_asset_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid parent comment")

    comment = MediaComment(
        media_asset_id=media_asset_id,
        user_id=author.id,
        content=text,
        parent_id=parent.id if parent else None,
    )
    db.add(comment)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add comment") from exc

    db.refresh(comment)
    return {
        "id": comment.id,
        "media_asset_id": comment.media_asset_id,
        "user_id": author.id,
        "username": author.username,
        "avatar_url": author.avatar_url,
        "role": getattr(author, "role", None),
        "content": comment.content,
        "parent_id": comment.parent_id,
        "created_at": comment.created_at,
        "replies": [],
    }


def delete_media_asset(
    db: Session,
    *,
    asset_id: UUID,
    delete_remote: bool = True,
) -> None:
    asset = db.get(MediaAsset, asset_id)
    if asset is None:
        return
    try:
        _delete_media_asset_objects(
            db,
            [asset],
            delete_remote=delete_remote,
            fail_on_remote_error=True,
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete media asset") from exc


def verify_media_asset(
    db: Session,
    *,
    asset_id: UUID,
    delete_remote: bool = True,
) -> dict[str, bool]:
    """Confirm the media asset is reachable, removing it if the file is gone."""

    asset = db.get(MediaAsset, asset_id)
    if asset is None:
        return {"deleted": False, "missing": True}

    if _media_asset_is_fetchable(asset):
        return {"deleted": False, "missing": False}

    try:
        removed = _delete_media_asset_objects(
            db,
            [asset],
            delete_remote=delete_remote,
            fail_on_remote_error=True,
        )
        db.commit()
        return {"deleted": removed > 0, "missing": True}
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to verify media asset") from exc


def delete_old_media(db: Session, *, older_than: timedelta | None = None) -> int:
    """Remove media metadata records older than the provided delta (default 2 days)."""

    cutoff = datetime.now(timezone.utc) - (older_than or timedelta(days=2))
    stmt = delete(MediaAsset).where(MediaAsset.created_at < cutoff).returning(MediaAsset.id)
    try:
        result = db.execute(stmt)
        removed = result.fetchall()
        db.commit()
        return len(removed)
    except SQLAlchemyError:
        db.rollback()
        return 0


def store_upload(upload: UploadFile, base_dir: Path) -> Tuple[str, str, str]:
    """Persist an uploaded file and return ``(relative_path, filename, content_type)``."""

    extension = Path(upload.filename or "").suffix
    generated_name = f"{uuid4().hex}{extension}"
    base_dir.mkdir(parents=True, exist_ok=True)
    destination = base_dir / generated_name
    upload.file.seek(0)
    with destination.open("wb") as fh:
        fh.write(upload.file.read())
    rel_path = os.path.relpath(destination, start=Path.cwd())
    return rel_path.replace(os.sep, "/"), generated_name, upload.content_type or "application/octet-stream"


__all__ = [
    "list_media_for_user",
    "list_media_feed",
    "set_media_like_state",
    "set_media_dislike_state",
    "list_media_comments",
    "create_media_comment",
    "delete_media_asset",
    "delete_old_media",
    "store_upload",
]
