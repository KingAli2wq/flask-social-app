"""Media upload endpoints that leverage DigitalOcean Spaces."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User
from ..schemas import MediaUploadResponse
from ..services import SpacesConfigurationError, SpacesUploadError, get_current_user, upload_file_to_spaces

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


    try:
        result = await upload_file_to_spaces(file, folder="media", db=db, user_id=current_user.id)
    except SpacesConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except SpacesUploadError as exc:  # pragma: no cover - network bound
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if result.asset_id is None:
        raise HTTPException(status_code=500, detail="Failed to persist media metadata")

    return MediaUploadResponse(
        id=result.asset_id,
        url=result.url,
        key=result.key,
        bucket=result.bucket,
        content_type=result.content_type,
    )
