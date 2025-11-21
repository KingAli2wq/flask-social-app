"""Business logic for working with posts stored in PostgreSQL."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import MediaAsset, Post, User
from .spaces_service import SpacesConfigurationError, SpacesUploadError, upload_file_to_spaces


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

    normalized_asset_id: UUID | None
    if isinstance(media_asset_id, UUID):
        normalized_asset_id = media_asset_id
    elif isinstance(media_asset_id, str):
        candidate = media_asset_id.strip()
        if not candidate:
            normalized_asset_id = None
        else:
            try:
                normalized_asset_id = UUID(candidate)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="media_asset_id must be a valid UUID") from exc
    else:
        normalized_asset_id = None

    if file is not None and normalized_asset_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a file upload or a media_asset_id, not both",
        )

    media_url: str | None = None
    if file is not None:
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

        media_url = upload_result.url
        normalized_asset_id = upload_result.asset_id
        if normalized_asset_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist media metadata",
            )

    asset: MediaAsset | None = None
    if normalized_asset_id is not None and file is None:
        asset = db.get(MediaAsset, normalized_asset_id)
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")
        if media_url is None:
            media_url = asset.url

    post = Post(user_id=user_id, caption=caption, media_url=media_url, media_asset_id=normalized_asset_id)
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def list_feed_records(db: Session) -> list[Post]:
    """Return the latest posts in reverse chronological order."""

    statement = select(Post).order_by(Post.created_at.desc())
    return list(db.scalars(statement))


def delete_post_record(db: Session, *, post_id: UUID, requester_id: UUID) -> None:
    """Delete a post if the requester is the author."""

    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.user_id != requester_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete this post")
    db.delete(post)
    db.commit()


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


__all__ = ["create_post_record", "list_feed_records", "delete_post_record", "delete_old_posts"]
