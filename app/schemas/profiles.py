"""Schemas for profile endpoints."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator

class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str | None
    bio: str | None
    location: str | None
    website: HttpUrl | None = None
    avatar_url: HttpUrl | str | None = None
    created_at: datetime
    last_active_at: datetime

    @field_validator("website", mode="before")
    def clean_website(cls, v):
        if v in (None, "", "None"):
            return None
        return v

class ProfileUpdateRequest(BaseModel):
    bio: str | None = None
    location: str | None = None
    website: HttpUrl | None = None
    avatar_url: HttpUrl | str | None = None



__all__ = ["ProfileResponse", "ProfileUpdateRequest"]
