"""Media upload endpoints plus immersive TikTok-style reel APIs."""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User
from ..schemas import (
    MediaCommentCreate,
    MediaCommentListResponse,
    MediaCommentResponse,
    MediaEngagementResponse,
    MediaFeedResponse,
    MediaUploadResponse,
    MediaVerificationResponse,
)
from ..services import (
    SpacesConfigurationError,
    SpacesUploadError,
    create_media_comment,
    get_current_user,
    get_optional_user,
    list_media_comments,
    list_media_feed,
    set_media_dislike_state,
    set_media_like_state,
    upload_file_to_spaces,
    verify_media_asset,
)

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media(
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MediaUploadResponse:
    """Upload media assets to Spaces, persist metadata, and return the stored asset."""

    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="Uploaded file must include a filename.")

    content_type = (file.content_type or "application/octet-stream").strip() or "application/octet-stream"

    user_id_value = getattr(current_user, "id", None)
    if user_id_value is None:
        raise HTTPException(status_code=500, detail="Authenticated user is missing an identifier.")
    if isinstance(user_id_value, uuid.UUID):
        user_id = user_id_value
    else:
        try:
            user_id = uuid.UUID(str(user_id_value))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=500, detail="Invalid user identifier.") from exc

    try:
        result = await upload_file_to_spaces(file, folder="media", db=db, user_id=user_id)
    except SpacesConfigurationError as exc:
        print("CONFIG ERROR:", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except SpacesUploadError as exc:
        print("UPLOAD ERROR:", exc)
        # Print inner exception if it exists
        if hasattr(exc, "__cause__") and exc.__cause__:
            print("CAUSE:", exc.__cause__)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        print("UNEXPECTED ERROR:", exc)
        raise


    if result.asset_id is None:
        raise HTTPException(status_code=500, detail="Failed to persist media metadata")

    return MediaUploadResponse(
        id=result.asset_id,
        url=result.url,
        key=result.key,
        bucket=result.bucket,
        content_type=result.content_type,
    )


@router.get("/feed", response_model=MediaFeedResponse)
async def list_media_feed_endpoint(
    limit: int = 25,
    db: Session = Depends(get_session),
    viewer: User | None = Depends(get_optional_user),
) -> MediaFeedResponse:
    records = list_media_feed(db, viewer_id=viewer.id if viewer else None, limit=limit)
    return MediaFeedResponse(items=records)


@router.post("/{asset_id}/likes", response_model=MediaEngagementResponse)
async def like_media_asset(
    asset_id: uuid.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MediaEngagementResponse:
    payload = set_media_like_state(db, media_asset_id=asset_id, user_id=current_user.id, should_like=True)
    return MediaEngagementResponse(**payload)


@router.delete("/{asset_id}/likes", response_model=MediaEngagementResponse)
async def unlike_media_asset(
    asset_id: uuid.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MediaEngagementResponse:
    payload = set_media_like_state(db, media_asset_id=asset_id, user_id=current_user.id, should_like=False)
    return MediaEngagementResponse(**payload)


@router.post("/{asset_id}/dislikes", response_model=MediaEngagementResponse)
async def dislike_media_asset(
    asset_id: uuid.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MediaEngagementResponse:
    payload = set_media_dislike_state(db, media_asset_id=asset_id, user_id=current_user.id, should_dislike=True)
    return MediaEngagementResponse(**payload)


@router.delete("/{asset_id}/dislikes", response_model=MediaEngagementResponse)
async def remove_dislike_media_asset(
    asset_id: uuid.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MediaEngagementResponse:
    payload = set_media_dislike_state(db, media_asset_id=asset_id, user_id=current_user.id, should_dislike=False)
    return MediaEngagementResponse(**payload)


@router.get("/{asset_id}/comments", response_model=MediaCommentListResponse)
async def list_media_comments_endpoint(
    asset_id: uuid.UUID,
    db: Session = Depends(get_session),
) -> MediaCommentListResponse:
    comments = list_media_comments(db, media_asset_id=asset_id)
    return MediaCommentListResponse(items=comments)


@router.post("/{asset_id}/comments", response_model=MediaCommentResponse)
async def create_media_comment_endpoint(
    asset_id: uuid.UUID,
    payload: MediaCommentCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MediaCommentResponse:
    record = create_media_comment(
        db,
        media_asset_id=asset_id,
        author=current_user,
        content=payload.content,
        parent_id=payload.parent_id,
    )
    return MediaCommentResponse(**record)


@router.post("/{asset_id}/verify", response_model=MediaVerificationResponse)
async def verify_media_asset_endpoint(
    asset_id: uuid.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MediaVerificationResponse:
    result = verify_media_asset(db, asset_id=asset_id, delete_remote=True)
    return MediaVerificationResponse(media_asset_id=asset_id, **result)
