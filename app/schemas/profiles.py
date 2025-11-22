"""Schemas for profile endpoints."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, HttpUrl


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str | None
    bio: str | None
    location: str | None
    website: HttpUrl | None = None
    avatar_url: str | None = None
    created_at: datetime
    last_active_at: datetime


class ProfileUpdateRequest(BaseModel):
    bio: str | None = None
    location: str | None = None
    website: HttpUrl | None = None



__all__ = ["ProfileResponse", "ProfileUpdateRequest"]
