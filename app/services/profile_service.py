from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import User
from ..schemas import ProfileUpdateRequest


def update_profile(db: Session, *, user_id: UUID, payload: ProfileUpdateRequest) -> User:
    """Apply profile updates for the supplied ``user_id``."""

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Only update fields that were actually sent by the client
    update_data = payload.model_dump(exclude_unset=True)

    # --- avatar_url handling ---
    # If the client sends avatar_url as a non-empty string, persist it.
    # If the client sends it as null/empty, ignore it and keep the existing one.
    if "avatar_url" in update_data:
        avatar = update_data["avatar_url"]
        if avatar in (None, "", "None"):
            # Do NOT overwrite the existing avatar with null/empty.
            update_data.pop("avatar_url", None)

    # --- website normalization ---
    if "website" in update_data:
        website = update_data["website"]
        if website in (None, "", "None"):
            update_data["website"] = None
        else:
            update_data["website"] = str(website)

    # Apply all remaining updates
    for field, value in update_data.items():
        setattr(user, field, value)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile",
        ) from exc

    db.refresh(user)
    return user
