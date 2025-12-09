"""Business logic for authentication and authorization backed by PostgreSQL."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User
from ..schemas import RegisterRequest
from ..security.secrets import MissingSecretError, require_secret

logger = logging.getLogger(__name__)

_security = HTTPBearer(auto_error=False)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
DEFAULT_TOKEN_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "1440"))


@lru_cache(maxsize=1)
def _get_jwt_secret() -> str:
    try:
        return require_secret("JWT_SECRET_KEY")
    except MissingSecretError as exc:
        raise RuntimeError(str(exc)) from exc


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""

    return _pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify that ``password`` matches ``hashed_password``."""

    try:
        return _pwd_context.verify(password, hashed_password)
    except Exception:  # pragma: no cover - passlib internal errors are rare
        logger.exception("Password verification failed due to an unexpected error")
        return False


def create_access_token(subject: UUID, *, expires_minutes: Optional[int] = None) -> str:
    """Create a signed JWT holding the provided ``subject``."""

    expire_delta = timedelta(minutes=expires_minutes or DEFAULT_TOKEN_MINUTES)
    now = datetime.now(timezone.utc)
    payload = {"sub": str(subject), "exp": now + expire_delta, "iat": now}
    token = jwt.encode(payload, _get_jwt_secret(), algorithm=ALGORITHM)
    return token


def decode_access_token(token: str) -> UUID:
    """Decode and validate a JWT, returning the embedded subject UUID."""

    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[ALGORITHM])
    except JWTError as exc:  # pragma: no cover - dependent on invalid tokens
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    try:
        return UUID(subject)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload") from exc


def register_user(db: Session, payload: RegisterRequest) -> Tuple[User, str]:
    """Persist a new user and return the user with an access token."""

    existing_username = db.scalar(select(User).where(User.username == payload.username))
    if existing_username:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already in use")

    if payload.email:
        existing_email = db.scalar(select(User).where(User.email == str(payload.email)))
        if existing_email:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    hashed = hash_password(payload.password)

    bio: str | None = payload.bio.strip() if payload.bio else None

    user = User(
        username=payload.username,
        email=str(payload.email) if payload.email else None,
        hashed_password=hashed,
        bio=bio,
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to register user")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to register user") from exc

    token = create_access_token(user.id)
    return user, token


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate a user against stored credentials."""

    user = db.scalar(select(User).where(User.username == username))
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
    db: Session = Depends(get_session),
) -> User:
    """Resolve the authenticated user from the provided bearer token."""

    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    user_id = decode_access_token(credentials.credentials)

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        user.last_active_at = datetime.now(timezone.utc)
        db.commit()
    except SQLAlchemyError:  # pragma: no cover - defensive logging
        db.rollback()
        logger.warning("Failed to update last_active_at for user %s", user.id)

    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
    db: Session = Depends(get_session),
) -> User | None:
    """Return the authenticated user when a bearer token is provided."""

    if not credentials or credentials.scheme.lower() != "bearer":
        return None

    try:
        user_id = decode_access_token(credentials.credentials)
    except HTTPException:
        return None

    return db.get(User, user_id)


def require_roles(*allowed_roles: str):
    normalized = {role.lower() for role in allowed_roles if role}

    async def _resolver(user: User = Depends(get_current_user)) -> User:
        role = (getattr(user, "role", None) or "user").lower()
        if normalized and role not in normalized:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _resolver


def require_owner():
    return require_roles("owner")


__all__ = [
    "register_user",
    "authenticate_user",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
    "get_current_user",
    "get_optional_user",
    "require_roles",
    "require_owner",
]
