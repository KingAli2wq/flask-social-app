"""Profile business logic."""
from __future__ import annotations

from fastapi import HTTPException, status

from ..database import FakeDatabase
from ..models import UserRecord
from ..schemas import ProfileUpdateRequest


def get_profile(db: FakeDatabase, username: str) -> UserRecord:
    user = db.get_user(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def update_profile(db: FakeDatabase, target: UserRecord, payload: ProfileUpdateRequest) -> UserRecord:
    db.update_user(
        target.username,
        bio=payload.bio,
        location=payload.location,
        website=str(payload.website) if payload.website else None,
    )
    updated = db.get_user(target.username)
    assert updated is not None
    return updated


__all__ = ["get_profile", "update_profile"]
