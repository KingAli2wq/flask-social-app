"""Schemas for media uploads to DigitalOcean Spaces."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class MediaUploadResponse(BaseModel):
    """Response returned after uploading a file to Spaces."""

    id: UUID = Field(..., description="Unique identifier for the persisted media asset")
    url: str = Field(..., description="Public URL of the uploaded asset")
    key: str = Field(..., description="Object key inside the Spaces bucket")
    bucket: str = Field(..., description="Target DigitalOcean Spaces bucket")
    content_type: str = Field(..., description="MIME type associated with the uploaded file")


__all__ = ["MediaUploadResponse"]
