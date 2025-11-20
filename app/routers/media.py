"""Media upload endpoints."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile

from ..models import UserRecord
from ..schemas import MediaUploadResponse
from ..services import get_current_user, store_upload

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media(
    file: UploadFile = File(...),
    current_user: UserRecord = Depends(get_current_user),
) -> MediaUploadResponse:
    # Using the current user is a placeholder for auditing/tracking
    base_dir = Path(os.getenv("MEDIA_ROOT", "media/uploads"))
    rel_path, filename, content_type = store_upload(file, base_dir)
    return MediaUploadResponse(path=rel_path, filename=filename, content_type=content_type)
