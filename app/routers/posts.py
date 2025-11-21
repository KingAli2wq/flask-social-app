"""Post related API routes backed by PostgreSQL and DigitalOcean Spaces."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User
from ..schemas import PostFeedResponse, PostResponse
from ..services import (
    SpacesUploadError,
    create_post_record,
    delete_post_record,
    list_feed_records,
    get_current_user,
    upload_file_to_spaces,
)

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post_endpoint(
    caption: str = Form(..., min_length=1),
    media_asset_id: UUID | None = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """Create a new post optionally storing an uploaded file in Spaces.

    The endpoint expects ``multipart/form-data`` when a file is supplied. If no
    file accompanies the request, the client may still submit a form payload
    containing only ``caption`` and ``user_id``.
    """

    media_url: str | None = None
    resolved_media_asset_id = media_asset_id
    if file is not None:
        if resolved_media_asset_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide either an uploaded file or a media_asset_id, not both",
            )
        try:
            upload_result = await upload_file_to_spaces(
                file, folder="posts", db=db, user_id=current_user.id
            )
        except SpacesUploadError as exc:  # pragma: no cover - network bound
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        media_url = upload_result.url
        resolved_media_asset_id = upload_result.asset_id
        if resolved_media_asset_id is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to persist media metadata")

    post = create_post_record(
        db,
        user_id=current_user.id,
        caption=caption,
        media_url=media_url,
        media_asset_id=resolved_media_asset_id,
    )
    return PostResponse.model_validate(post)


@router.get("/feed", response_model=PostFeedResponse)
async def feed_endpoint(db: Session = Depends(get_session)) -> PostFeedResponse:
    posts = [PostResponse.model_validate(item) for item in list_feed_records(db)]
    return PostFeedResponse(items=posts)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post_endpoint(
    post_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    delete_post_record(db, post_id=post_id, requester_id=current_user.id)
