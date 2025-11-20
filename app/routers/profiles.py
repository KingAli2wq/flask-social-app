"""Profile API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..database import FakeDatabase, get_database
from ..models import UserRecord
from ..schemas import ProfileResponse, ProfileUpdateRequest
from ..services import get_current_user, get_profile, update_profile

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _to_profile_response(user: UserRecord) -> ProfileResponse:
    return ProfileResponse(
        username=user.username,
        email=user.email,
        bio=user.bio,
        location=user.location,
        website=user.website,
        created_at=user.created_at,
        last_active_at=user.last_active_at,
    )


@router.get("/{username}", response_model=ProfileResponse)
async def retrieve_profile(
    username: str,
    db: FakeDatabase = Depends(get_database),
) -> ProfileResponse:
    user = get_profile(db, username)
    return _to_profile_response(user)


@router.put("/me", response_model=ProfileResponse)
async def update_my_profile(
    payload: ProfileUpdateRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: FakeDatabase = Depends(get_database),
) -> ProfileResponse:
    updated = update_profile(db, current_user, payload)
    return _to_profile_response(updated)
