"""Media persistence and storage helpers for the social app."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..db import MediaAsset


def list_media_for_user(db: Session, user_id: UUID) -> list[MediaAsset]:
    """Return media assets uploaded by the specified user."""

    stmt = select(MediaAsset).where(MediaAsset.user_id == user_id).order_by(MediaAsset.created_at.desc())
    return list(db.scalars(stmt))


def delete_old_media(db: Session, *, older_than: timedelta | None = None) -> int:
    """Remove media metadata records older than the provided delta (default 2 days)."""

    cutoff = datetime.now(timezone.utc) - (older_than or timedelta(days=2))
    stmt = delete(MediaAsset).where(MediaAsset.created_at < cutoff).returning(MediaAsset.id)
    try:
        result = db.execute(stmt)
        removed = result.fetchall()
        db.commit()
        return len(removed)
    except SQLAlchemyError:
        db.rollback()
        return 0


def store_upload(upload: UploadFile, base_dir: Path) -> Tuple[str, str, str]:
    """Persist an uploaded file and return ``(relative_path, filename, content_type)``."""

    extension = Path(upload.filename or "").suffix
    generated_name = f"{uuid4().hex}{extension}"
    base_dir.mkdir(parents=True, exist_ok=True)
    destination = base_dir / generated_name
    upload.file.seek(0)
    with destination.open("wb") as fh:
        fh.write(upload.file.read())
    rel_path = os.path.relpath(destination, start=Path.cwd())
    return rel_path.replace(os.sep, "/"), generated_name, upload.content_type or "application/octet-stream"


__all__ = ["list_media_for_user", "delete_old_media", "store_upload"]
