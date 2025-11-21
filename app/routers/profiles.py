"""Profile API routes backed by PostgreSQL."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_session
from ..db import User
from ..schemas import ProfileResponse, ProfileUpdateRequest
from ..services import get_current_user, get_profile, update_profile

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/{username}", response_model=ProfileResponse)
async def retrieve_profile(
    username: str,
    db: Session = Depends(get_session),
) -> ProfileResponse:
    user = get_profile(db, username)
    return ProfileResponse.model_validate(user)


@router.put("/me", response_model=ProfileResponse)
async def update_my_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ProfileResponse:
    updated = update_profile(db, user_id=current_user.id, payload=payload)
    return ProfileResponse.model_validate(updated)
