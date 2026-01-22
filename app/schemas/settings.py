"""Schemas backing the settings API."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class SettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    role: str = "user"
    display_name: str | None = None
    email: EmailStr | None = None
    email_verified: bool
    email_verified_at: datetime | None = None
    email_verification_sent_at: datetime | None = None
    bio: str | None = None
    location: str | None = None
    website: HttpUrl | str | None = None
    email_dm_notifications: bool = False
    allow_friend_requests: bool = True
    dm_followers_only: bool = False
    language_preference: str = "en"
    language_options: dict[str, str] = Field(default_factory=dict)


class AdminAiModerationSettingsResponse(BaseModel):
    enabled: bool
    source: str
    model: str
    base_url: str
    cloud: bool
    auth_configured: bool | None = None


class AdminAiModerationSettingsUpdate(BaseModel):
    enabled: bool


class SettingsProfileUpdate(BaseModel):
    display_name: str | None = None
    username: str | None = None
    bio: str | None = None
    location: str | None = None
    website: HttpUrl | None = None


class SettingsContactUpdate(BaseModel):
    email: EmailStr


class SettingsPreferencesUpdate(BaseModel):
    email_dm_notifications: bool | None = None
    allow_friend_requests: bool | None = None
    dm_followers_only: bool | None = None
    language_preference: str | None = None


class SettingsPasswordUpdate(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


class EmailVerificationConfirmRequest(BaseModel):
    code: str


class EmailVerificationResponse(BaseModel):
    expires_at: datetime | None = None
    cooldown_seconds: int = 0


__all__ = [
    "SettingsResponse",
    "SettingsProfileUpdate",
    "SettingsContactUpdate",
    "SettingsPreferencesUpdate",
    "SettingsPasswordUpdate",
    "EmailVerificationConfirmRequest",
    "EmailVerificationResponse",
    "AdminAiModerationSettingsResponse",
    "AdminAiModerationSettingsUpdate",
]
