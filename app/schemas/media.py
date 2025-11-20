"""Schemas for media uploads."""
from __future__ import annotations

from pydantic import BaseModel


class MediaUploadResponse(BaseModel):
    path: str
    filename: str
    content_type: str


__all__ = ["MediaUploadResponse"]
