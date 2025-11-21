"""Media upload endpoints that leverage DigitalOcean Spaces."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..schemas import MediaUploadResponse
from ..services import SpacesUploadError, upload_file_to_spaces

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media(file: UploadFile = File(...)) -> MediaUploadResponse:
    """Upload media assets to Spaces and provide their public URL."""

    try:
        result = await upload_file_to_spaces(file, folder="media")
    except SpacesUploadError as exc:  # pragma: no cover - network bound
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return MediaUploadResponse(url=result.url, key=result.key, bucket=result.bucket, content_type=result.content_type)
