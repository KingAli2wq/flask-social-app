"""Post related API routes backed by PostgreSQL and DigitalOcean Spaces."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User
from ..schemas import PostFeedResponse, PostResponse
from ..services import (
    create_post_record,
    delete_post_record,
    get_current_user,
    get_optional_user,
    list_feed_records,
)
from ..services.realtime import feed_updates_manager

router = APIRouter(prefix="/posts", tags=["posts"])

logger = logging.getLogger(__name__)


@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post_endpoint(
    caption: str = Form(..., min_length=1),
    media_asset_id: Optional[str] = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """Create a new post optionally storing an uploaded file in Spaces.

    The endpoint expects ``multipart/form-data`` when a file is supplied. If no
    file accompanies the request, the client may still submit a form payload
    containing only ``caption`` and ``user_id``.
    """

    if media_asset_id is not None and media_asset_id.strip() == "":
        media_asset_id = None

    if file is not None and media_asset_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a file upload or a media_asset_id, not both",
        )

    post = await create_post_record(
        db,
        user_id=current_user.id,
        caption=caption,
        media_asset_id=media_asset_id,
        file=file,
    )

    try:
        await feed_updates_manager.broadcast(
            {
                "type": "post_created",
                "post_id": str(post.id),
                "user_id": str(current_user.id),
                "created_at": post.created_at.isoformat() if getattr(post, "created_at", None) else None,
            }
        )
    except Exception:  # pragma: no cover - best effort logging
        logger.exception("Failed to broadcast feed update")

    return PostResponse.model_validate(post)


@router.get("/feed", response_model=PostFeedResponse)
async def feed_endpoint(
    db: Session = Depends(get_session),
    current_user: User | None = Depends(get_optional_user),
) -> PostFeedResponse:
    viewer_id = current_user.id if current_user else None
    posts = [PostResponse.model_validate(item) for item in list_feed_records(db, viewer_id=viewer_id)]
    return PostFeedResponse(items=posts)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post_endpoint(
    post_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    delete_post_record(db, post_id=post_id, requester_id=current_user.id)
