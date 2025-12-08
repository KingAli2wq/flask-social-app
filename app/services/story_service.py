"""Business logic for ephemeral stories."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Follow, MediaAsset, Story, User

_ALLOWED_POSITIONS = {"top-left", "top-right", "bottom-left", "bottom-right", "center"}
_DEFAULT_POSITION = "bottom-left"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_viewer_filter(viewer_id: UUID | None) -> Select[tuple[UUID]] | None:
    if viewer_id is None:
        return None
    return select(Follow.following_id).where(Follow.follower_id == viewer_id)


def list_active_stories(db: Session, *, viewer_id: UUID | None) -> list[dict[str, Any]]:
    if viewer_id is None:
        return []

    cutoff = _now()
    follow_subquery = _build_viewer_filter(viewer_id)

    statement = (
        select(Story, User)
        .join(User, Story.user_id == User.id)
        .where(Story.expires_at > cutoff)
    )

    if follow_subquery is not None:
        statement = statement.where((Story.user_id == viewer_id) | (Story.user_id.in_(follow_subquery)))

    statement = statement.order_by(Story.created_at.desc())

    grouped: dict[UUID, dict[str, Any]] = {}
    for story, author in db.execute(statement).all():
        author_id = author.id
        bucket = grouped.get(author_id)
        if bucket is None:
            bucket = {
                "user": {
                    "id": author.id,
                    "username": author.username,
                    "display_name": author.display_name,
                    "avatar_url": author.avatar_url,
                },
                "stories": [],
            }
            grouped[author_id] = bucket
        bucket["stories"].append(
            {
                "id": story.id,
                "media_url": story.media_url,
                "media_content_type": story.media_content_type,
                "text_overlay": story.text_overlay,
                "text_color": story.text_color,
                "text_background": story.text_background,
                "text_position": story.text_position,
                "text_font_size": story.text_font_size,
                "created_at": story.created_at,
                "expires_at": story.expires_at,
            }
        )

    ordered = sorted(grouped.values(), key=lambda item: item["stories"][0]["created_at"], reverse=True)
    return ordered


def create_story(
    db: Session,
    *,
    user_id: UUID,
    media_asset_id: UUID,
    text_overlay: str | None = None,
    text_color: str | None = None,
    text_background: str | None = None,
    text_position: str | None = None,
    text_font_size: int | None = None,
    expires_in_hours: int = 24,
) -> Story:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    asset = db.get(MediaAsset, media_asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    media_url_value = getattr(asset, "url", None)
    if not media_url_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Media asset is missing a URL")
    media_content_type = getattr(asset, "content_type", None)

    normalized_overlay = (text_overlay or "").strip() or None
    normalized_color = (text_color or "").strip() or None
    normalized_background = (text_background or "").strip() or None
    normalized_position = (text_position or "").strip().lower() or _DEFAULT_POSITION
    if normalized_position not in _ALLOWED_POSITIONS:
        normalized_position = _DEFAULT_POSITION
    try:
        normalized_font = int(text_font_size) if text_font_size is not None else 22
    except (TypeError, ValueError):
        normalized_font = 22
    normalized_font = max(12, min(48, normalized_font))

    now = _now()
    expires_at = now + timedelta(hours=max(1, expires_in_hours))

    story = Story(
        user_id=user_id,
        media_asset_id=media_asset_id,
        media_url=media_url_value,
        media_content_type=media_content_type,
        text_overlay=normalized_overlay,
        text_color=normalized_color,
        text_background=normalized_background,
        text_position=normalized_position,
        text_font_size=normalized_font,
        created_at=now,
        expires_at=expires_at,
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


__all__ = ["create_story", "list_active_stories"]
