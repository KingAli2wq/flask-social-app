"""Schemas for profile endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, HttpUrl


class ProfileResponse(BaseModel):
    username: str
    email: str | None
    bio: str | None
    location: str | None
    website: HttpUrl | None = None
    created_at: datetime
    last_active_at: datetime


class ProfileUpdateRequest(BaseModel):
    bio: str | None = None
    location: str | None = None
    website: HttpUrl | None = None


__all__ = ["ProfileResponse", "ProfileUpdateRequest"]
