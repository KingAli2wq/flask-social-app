"""Profile API routes backed by PostgreSQL."""
from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db, get_session
from ..models import User
from ..schemas import ProfileResponse, ProfileUpdateRequest
from ..services import get_current_user, get_profile, update_profile
from ..services.spaces_service import upload_file_to_spaces   # NEW IMPORT

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
# Update the logged-in user's profile — FIXED to support avatar upload
# ---------------------------------------------------------------------------
@router.put("/me", response_model=ProfileResponse)
async def update_my_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ProfileResponse:
    """
    Update the logged-in user's profile fields.
    Avatar uploads now properly save into the "media/" folder in Spaces.
    """
    updated = update_profile(db, user_id=cast(UUID, current_user.id), payload=payload)
    return ProfileResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# Avatar upload endpoint — REQUIRED FIX
# ---------------------------------------------------------------------------
@router.post("/me/avatar", response_model=dict)
async def upload_my_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """
    Uploads a new avatar to Spaces under /media/.
    Returns the URL so the front-end can PATCH /profiles/me with avatar_url.
    """
    upload_result = await upload_file_to_spaces(
        file,
        folder="media",              # <<<<<<<< FIX: FORCE MEDIA FOLDER
        db=db,
        user_id=cast(UUID, current_user.id),
    )

    return {"url": upload_result.url}


# ---------------------------------------------------------------------------
# Retrieve profile by UUID user_id (required by feed front-end)
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


@router.post("/fix-website-field")
def fix_website_field(db=Depends(get_db)):
    db.execute(text(
        """
        UPDATE users
        SET website = NULL
        WHERE website = 'None'
           OR website = ''
           OR (website IS NOT NULL AND website NOT LIKE 'http%');
    """
    ))
    db.commit()
    return {"status": "DONE"}
