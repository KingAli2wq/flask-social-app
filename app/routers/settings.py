"""Account settings API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User
from ..schemas import (
    EmailVerificationConfirmRequest,
    EmailVerificationResponse,
    SettingsContactUpdate,
    SettingsPasswordUpdate,
    SettingsPreferencesUpdate,
    SettingsProfileUpdate,
    SettingsResponse,
)
from ..services import get_current_user
from ..services.settings_service import (
    build_settings_response,
    confirm_email_verification,
    request_email_verification,
    update_contact_settings,
    update_password,
    update_preferences,
    update_profile_settings,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def _get_fresh_user(db: Session, user: User) -> User:
    instance = db.get(User, user.id)
    if not instance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return instance


@router.get("/me", response_model=SettingsResponse)
async def read_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> SettingsResponse:
    user = _get_fresh_user(db, current_user)
    return build_settings_response(user)


@router.patch("/profile", response_model=SettingsResponse)
async def update_profile(
    payload: SettingsProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> SettingsResponse:
    user = _get_fresh_user(db, current_user)
    updated = update_profile_settings(db, user, payload)
    return build_settings_response(updated)


@router.patch("/contact", response_model=SettingsResponse)
async def update_contact(
    payload: SettingsContactUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> SettingsResponse:
    user = _get_fresh_user(db, current_user)
    updated = update_contact_settings(db, user, payload)
    return build_settings_response(updated)


@router.patch("/preferences", response_model=SettingsResponse)
async def update_user_preferences(
    payload: SettingsPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> SettingsResponse:
    user = _get_fresh_user(db, current_user)
    updated = update_preferences(db, user, payload)
    return build_settings_response(updated)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: SettingsPasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> None:
    user = _get_fresh_user(db, current_user)
    update_password(db, user, payload)


@router.post("/email/request", response_model=EmailVerificationResponse)
async def request_verification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> EmailVerificationResponse:
    user = _get_fresh_user(db, current_user)
    return request_email_verification(db, user)


@router.post("/email/confirm", response_model=SettingsResponse)
async def confirm_verification(
    payload: EmailVerificationConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> SettingsResponse:
    user = _get_fresh_user(db, current_user)
    updated = confirm_email_verification(db, user, payload)
    return build_settings_response(updated)


__all__ = ["router"]
