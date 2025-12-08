"""API routes for ephemeral stories."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import User
from app.schemas import StoryAuthor, StoryBucket, StoryCreate, StoryFeedResponse, StoryItem
from app.services import create_story, get_current_user, get_optional_user, list_active_stories

router = APIRouter(prefix="/stories", tags=["stories"])


def _serialize_story(story) -> StoryItem:
    return StoryItem(
        id=story.id,
        media_url=story.media_url,
        media_content_type=story.media_content_type,
        text_overlay=story.text_overlay,
        text_color=story.text_color,
        text_background=story.text_background,
        text_position=story.text_position,
        text_font_size=story.text_font_size,
        created_at=story.created_at,
        expires_at=story.expires_at,
    )


def _normalize_uuid(value) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


@router.get("/feed", response_model=StoryFeedResponse)
async def list_story_feed(
    db: Session = Depends(get_session),
    viewer: User | None = Depends(get_optional_user),
) -> StoryFeedResponse:
    viewer_id: UUID | None = None
    if viewer is not None and getattr(viewer, "id", None) is not None:
        viewer_id = _normalize_uuid(viewer.id)
    buckets = []
    for entry in list_active_stories(db, viewer_id=viewer_id):
        buckets.append(
            StoryBucket(
                user=StoryAuthor(**entry["user"]),
                stories=[StoryItem(**story) for story in entry["stories"]],
            )
        )
    return StoryFeedResponse(items=buckets)


@router.post("/", response_model=StoryItem, status_code=status.HTTP_201_CREATED)
async def create_story_endpoint(
    payload: StoryCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> StoryItem:
    user_id = _normalize_uuid(current_user.id)
    story = create_story(
        db,
        user_id=user_id,
        media_asset_id=payload.media_asset_id,
        text_overlay=payload.text_overlay,
        text_color=payload.text_color,
        text_background=payload.text_background,
        text_position=payload.text_position,
        text_font_size=payload.text_font_size,
    )
    return _serialize_story(story)
