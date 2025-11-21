"""Business logic for working with posts stored in PostgreSQL."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..db import MediaAsset, Post, User


def create_post_record(
    db: Session,
    *,
    user_id: UUID,
    content: str,
    media_url: str | None,
    media_asset_id: UUID | None = None,
) -> Post:
    """Create and persist a new post for the given user."""

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if media_asset_id is not None:
        asset = db.get(MediaAsset, media_asset_id)
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")
        if media_url is None:
            media_url = asset.url

    post = Post(user_id=user_id, content=content, media_url=media_url, media_asset_id=media_asset_id)
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
