"""Profile business logic backed by PostgreSQL."""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..db import User
from ..schemas import ProfileUpdateRequest


def get_profile(db: Session, username: str) -> User:
    """Return the persisted user matching ``username`` or raise 404."""

    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def update_profile(db: Session, *, user_id: UUID, payload: ProfileUpdateRequest) -> User:
    """Apply profile updates for the supplied ``user_id``."""

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "website" in update_data and update_data["website"] is not None:
        update_data["website"] = str(update_data["website"])

    if update_data:
        for field, value in update_data.items():
            setattr(user, field, value)
        try:
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update profile") from exc

    db.refresh(user)
    return user


__all__ = ["get_profile", "update_profile"]
