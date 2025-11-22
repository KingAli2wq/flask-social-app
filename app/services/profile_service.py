"""Profile business logic backed by PostgreSQL."""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import User
from ..schemas import ProfileUpdateRequest


def get_profile(db: Session, username: str) -> User:
    """Return the persisted user matching ``username`` or raise 404."""

    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def update_profile(db: Session, *, user_id: UUID, payload: ProfileUpdateRequest) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    update_data = payload.model_dump(exclude_none=True)

    # CRITICAL FIX: do NOT wipe avatar_url if frontend didn't send it
    if "avatar_url" in update_data:
        if not update_data["avatar_url"]:
            # Skip null/empty avatar
            update_data.pop("avatar_url")
    else:
        # Explicitly preserve existing avatar_url
        update_data["avatar_url"] = user.avatar_url

    # Normalize website
    if "website" in update_data:
        if update_data["website"] in ("", None, "None"):
            update_data["website"] = None
        else:
            update_data["website"] = str(update_data["website"])

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user





__all__ = ["get_profile", "update_profile"]
