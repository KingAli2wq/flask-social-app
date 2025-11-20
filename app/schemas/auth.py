"""Pydantic schemas for authentication endpoints."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)
    email: EmailStr | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserPublicProfile(BaseModel):
    username: str
    email: EmailStr | None = None
    bio: str | None = None
    location: str | None = None
    website: str | None = None