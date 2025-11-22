"""Profile API routes backed by PostgreSQL."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User
from ..schemas import ProfileResponse, ProfileUpdateRequest
from ..services import get_current_user, get_profile, update_profile

router = APIRouter(prefix="/profiles", tags=["profiles"])


# ---------------------------------------------------------------------------
# Retrieve profile by USERNAME (existing route)
# ---------------------------------------------------------------------------
@router.get("/{username}", response_model=ProfileResponse)
async def retrieve_profile(
    username: str,
    db: Session = Depends(get_session),
) -> ProfileResponse:
    """
    Fetch a user profile using their username.
    This is required for profile pages like /profiles/<username>.
    """
    user = get_profile(db, username)
    return ProfileResponse.model_validate(user)


# ---------------------------------------------------------------------------
# Update the logged-in user's profile
# ---------------------------------------------------------------------------
@router.put("/me", response_model=ProfileResponse)
async def update_my_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ProfileResponse:
    """
    Update the logged-in user's profile fields (bio, website, location, avatar_url).
    """
    updated = update_profile(db, user_id=current_user.id, payload=payload)
    return ProfileResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# NEW: Retrieve profile by UUID user_id (required by feed front-end)
# ---------------------------------------------------------------------------
@router.get("/by-id/{user_id}", response_model=ProfileResponse)
async def retrieve_profile_by_id(
    user_id: str,
    db: Session = Depends(get_session),
) -> ProfileResponse:
    """
    Fetch a user profile using internal UUID (user_id).
    REQUIRED for feed avatar hydration because posts return user_id, not username.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return ProfileResponse.model_validate(user)
