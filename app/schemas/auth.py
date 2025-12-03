"""Pydantic schemas for authentication endpoints."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)
    email: EmailStr | None = None
    bio: str | None = Field(default=None, max_length=500)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    user_id: UUID
    token_type: str = "bearer"
    bio: str | None = None
    role: str | None = None


class UserPublicProfile(BaseModel):
    username: str
    email: EmailStr | None = None
    bio: str | None = None
    location: str | None = None
    website: str | None = None