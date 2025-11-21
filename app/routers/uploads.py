"""Standalone upload endpoint leveraging DigitalOcean Spaces."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_session
from ..db import User
from ..schemas import MediaUploadResponse
from ..services import SpacesUploadError, get_current_user, upload_file_to_spaces

router = APIRouter(tags=["uploads"])


@router.post("/upload/", response_model=MediaUploadResponse)
async def upload_endpoint(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> MediaUploadResponse:
    """Upload to DigitalOcean Spaces and return a public URL.

    The uploaded object is stored with public-read access so clients can reach it via HTTPS.
    Storage failures raise ``HTTPException`` with status 502 to signal upstream problems.
    """

    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="Uploaded file must include a filename.")

    content_type = (file.content_type or "application/octet-stream").strip() or "application/octet-stream"
    file.content_type = content_type

    try:
        result = await upload_file_to_spaces(file, folder="uploads", db=db, user_id=current_user.id)
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
