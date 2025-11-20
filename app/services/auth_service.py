"""Business logic for authentication and authorization."""
from __future__ import annotations

import hashlib
import secrets
from typing import Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..database import FakeDatabase, get_database
from ..models import UserRecord
from ..schemas import RegisterRequest

_security = HTTPBearer(auto_error=False)
_TOKENS: Dict[str, str] = {}


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _verify_password(password: str, password_hash: str) -> bool:
    return secrets.compare_digest(_hash_password(password), password_hash)


def register_user(db: FakeDatabase, payload: RegisterRequest) -> UserRecord:
    if db.get_user(payload.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already in use")
    record = UserRecord(
        username=payload.username,
        password_hash=_hash_password(payload.password),
        email=str(payload.email) if payload.email else None,
    )
    db.create_user(record)
    return record


def authenticate_user(db: FakeDatabase, username: str, password: str) -> Optional[UserRecord]:
    user = db.get_user(username)
    if not user:
        return None
    if not _verify_password(password, user.password_hash):
        return None
    return user


def issue_token(user: UserRecord) -> str:
    token = secrets.token_hex(32)
    _TOKENS[token] = user.username
    return token


def revoke_token(token: str) -> None:
    _TOKENS.pop(token, None)


def resolve_user_by_token(db: FakeDatabase, token: str) -> Optional[UserRecord]:
    username = _TOKENS.get(token)
    if not username:
        return None
    return db.get_user(username)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
    db: FakeDatabase = Depends(get_database),
) -> UserRecord:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = credentials.credentials
    user = resolve_user_by_token(db, token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user


__all__ = [
    "register_user",
    "authenticate_user",
    "issue_token",
    "revoke_token",
    "resolve_user_by_token",
    "get_current_user",
]
