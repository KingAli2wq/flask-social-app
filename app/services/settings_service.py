"""Business logic for account settings management."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from typing import cast

from ..config import get_settings
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
from .auth_service import hash_password, verify_password
from .email_service import EmailDeliveryError, send_email
from .translation_service import DEFAULT_LANGUAGE, normalize_language_preference, supported_languages

_VERIFICATION_CODE_TTL = timedelta(minutes=15)
_VERIFICATION_RESEND_COOLDOWN = timedelta(minutes=2)


def _resolve_language_preference(preference: str | None) -> str:
    try:
        return normalize_language_preference(preference)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_settings_response(user: User) -> SettingsResponse:
    lang_pref = _resolve_language_preference(cast(str | None, getattr(user, "language_preference", None)))
    return SettingsResponse(
        id=cast(UUID, user.id),
        username=cast(str, user.username),
        role=str(getattr(user, "role", None) or "user"),
        display_name=cast(str | None, user.display_name),
        email=cast(str | None, user.email),
        email_verified=bool(cast(datetime | None, user.email_verified_at)),
        email_verified_at=cast(datetime | None, user.email_verified_at),
        email_verification_sent_at=cast(datetime | None, user.email_verification_sent_at),
        bio=cast(str | None, user.bio),
        location=cast(str | None, user.location),
        website=cast(str | None, user.website),
        email_dm_notifications=bool(cast(bool | None, user.email_dm_notifications)),
        allow_friend_requests=bool(cast(bool | None, user.allow_friend_requests)),
        dm_followers_only=bool(cast(bool | None, user.dm_followers_only)),
        language_preference=lang_pref or DEFAULT_LANGUAGE,
        language_options=supported_languages(),
    )


def update_profile_settings(db: Session, user: User, payload: SettingsProfileUpdate) -> User:
    update_data = payload.model_dump(exclude_unset=True)

    if "username" in update_data and update_data["username"] != user.username:
        new_username = update_data["username"].strip()
        if len(new_username) < 3 or len(new_username) > 150:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username must be between 3 and 150 characters")
        update_data["username"] = new_username
        existing = db.scalar(select(User).where(User.username == new_username, User.id != user.id))
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    if "display_name" in update_data:
        display_name = (update_data["display_name"] or "").strip() or None
        if display_name and len(display_name) > 150:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Display name is too long")
        update_data["display_name"] = display_name

    if "bio" in update_data and update_data["bio"] is not None:
        update_data["bio"] = update_data["bio"].strip() or None
    if "location" in update_data and update_data["location"] is not None:
        update_data["location"] = update_data["location"].strip() or None

    for field, value in update_data.items():
        setattr(user, field, value)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update profile") from exc

    db.refresh(user)
    return user


def update_contact_settings(db: Session, user: User, payload: SettingsContactUpdate) -> User:
    new_email = str(payload.email).strip().lower()
    if not new_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email cannot be empty")

    existing = db.scalar(select(User).where(User.email == new_email, User.id != user.id))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    email_changed = new_email != (user.email or "").lower()
    setattr(user, "email", new_email)
    if email_changed:
        setattr(user, "email_verified_at", None)
        setattr(user, "email_verification_code", None)
        setattr(user, "email_verification_sent_at", None)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update email") from exc

    db.refresh(user)
    return user


def update_preferences(db: Session, user: User, payload: SettingsPreferencesUpdate) -> User:
    update_data = payload.model_dump(exclude_unset=True)
    if "language_preference" in update_data:
        update_data["language_preference"] = _resolve_language_preference(update_data.get("language_preference"))
    for field, value in update_data.items():
        setattr(user, field, value)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update preferences") from exc

    db.refresh(user)
    return user


def update_password(db: Session, user: User, payload: SettingsPasswordUpdate) -> None:
    hashed_password = cast(str, user.hashed_password)
    if not verify_password(payload.current_password, hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be different")

    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

    if len(payload.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")

    setattr(user, "hashed_password", hash_password(payload.new_password))

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update password") from exc


def request_email_verification(db: Session, user: User) -> EmailVerificationResponse:
    email = cast(str | None, user.email)
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Add an email before verifying")

    now = _now()
    sent_at = cast(datetime | None, user.email_verification_sent_at)
    if sent_at:
        elapsed = now - sent_at
        if elapsed < _VERIFICATION_RESEND_COOLDOWN:
            remaining = int((_VERIFICATION_RESEND_COOLDOWN - elapsed).total_seconds())
            return EmailVerificationResponse(expires_at=None, cooldown_seconds=remaining)

    code = _generate_code()
    setattr(user, "email_verification_code", code)
    setattr(user, "email_verification_sent_at", now)
    setattr(user, "email_verified_at", None)

    settings = get_settings()
    subject = "Verify your email for SocialSphere"
    body = (
        f"Hi {user.display_name or user.username},\n\n"
        f"Your verification code is {code}.\n"
        f"This code expires in {_VERIFICATION_CODE_TTL.total_seconds() / 60:.0f} minutes.\n\n"
        f"If you did not request this, you can ignore this email.\n\n"
        f"Visit {settings.public_base_url}/settings to enter the code."
    )

    try:
        send_email(email, subject, body)
    except EmailDeliveryError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to send verification email")

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to queue verification email") from exc

    expires_at = now + _VERIFICATION_CODE_TTL
    return EmailVerificationResponse(expires_at=expires_at, cooldown_seconds=int(_VERIFICATION_RESEND_COOLDOWN.total_seconds()))


def confirm_email_verification(db: Session, user: User, payload: EmailVerificationConfirmRequest) -> User:
    stored_code = cast(str | None, user.email_verification_code)
    if not stored_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No verification requested")

    sent_at = cast(datetime | None, user.email_verification_sent_at)
    if not sent_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification expired")

    now = _now()
    if now - sent_at > _VERIFICATION_CODE_TTL:
        setattr(user, "email_verification_code", None)
        setattr(user, "email_verification_sent_at", None)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code expired")

    if payload.code.strip() != stored_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    setattr(user, "email_verified_at", now)
    setattr(user, "email_verification_code", None)
    setattr(user, "email_verification_sent_at", None)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update verification status") from exc

    db.refresh(user)
    return user


__all__ = [
    "build_settings_response",
    "update_profile_settings",
    "update_contact_settings",
    "update_preferences",
    "update_password",
    "request_email_verification",
    "confirm_email_verification",
]
