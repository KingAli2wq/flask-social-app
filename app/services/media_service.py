"""Media file helper utilities."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple
from uuid import uuid4

from fastapi import UploadFile


def store_upload(upload: UploadFile, base_dir: Path) -> Tuple[str, str, str]:
    """Persist an uploaded file and return (relative_path, filename, content_type)."""
    extension = Path(upload.filename or "").suffix
    generated_name = f"{uuid4().hex}{extension}"
    base_dir.mkdir(parents=True, exist_ok=True)
    destination = base_dir / generated_name
    upload.file.seek(0)
    with destination.open("wb") as fh:
        fh.write(upload.file.read())
    rel_path = os.path.relpath(destination, start=Path.cwd())
    return rel_path.replace(os.sep, "/"), generated_name, upload.content_type or "application/octet-stream"


__all__ = ["store_upload"]
