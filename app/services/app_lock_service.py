"""Server-side app lock helpers.

This is a lightweight "app-wide password" gate intended to block access to API routes
unless an unlock cookie is present. It is not a substitute for user authentication.
"""

from __future__ import annotations

import hmac
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from jose import JWTError, jwt

from ..security.secrets import MissingSecretError, is_placeholder, require_secret

_LOCK_COOKIE_NAME = "socialsphere_app_lock"
_LOCK_SUBJECT = "app_lock"
_LOCK_TOKEN_TYPE = "app_lock"


def lock_cookie_name() -> str:
    return _LOCK_COOKIE_NAME


def is_app_lock_enabled() -> bool:
    value = os.getenv("APP_LOCK_PASSWORD")
    return not is_placeholder(value)


@lru_cache(maxsize=1)
def _get_lock_password() -> str:
    value = os.getenv("APP_LOCK_PASSWORD")
    if is_placeholder(value):
        raise MissingSecretError("Environment variable APP_LOCK_PASSWORD is required")
    assert value is not None
    return value.strip()


@lru_cache(maxsize=1)
def _get_lock_secret() -> str:
    """Return a secret for signing lock tokens.

    Prefer a dedicated secret, but fall back to JWT_SECRET_KEY to avoid additional
    configuration for existing deployments.
    """

    explicit = os.getenv("APP_LOCK_SECRET_KEY")
    if not is_placeholder(explicit):
        assert explicit is not None
        return explicit.strip()

    try:
        return require_secret("JWT_SECRET_KEY")
    except MissingSecretError as exc:
        raise RuntimeError(
            "APP_LOCK is enabled but no signing secret is available; set APP_LOCK_SECRET_KEY or JWT_SECRET_KEY"
        ) from exc


def verify_app_lock_password(provided: str) -> bool:
    """Constant-time comparison against APP_LOCK_PASSWORD."""

    try:
        required = _get_lock_password()
    except MissingSecretError:
        return False

    provided_norm = (provided or "").strip()
    return hmac.compare_digest(provided_norm, required)


def _token_ttl_minutes() -> int:
    raw = os.getenv("APP_LOCK_TTL_MINUTES", "720")
    try:
        ttl = int(raw)
    except ValueError:
        ttl = 720
    return max(5, min(ttl, 60 * 24 * 14))


def create_app_lock_token() -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=_token_ttl_minutes())
    payload = {
        "sub": _LOCK_SUBJECT,
        "typ": _LOCK_TOKEN_TYPE,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, _get_lock_secret(), algorithm=os.getenv("JWT_ALGORITHM", "HS256"))


def is_unlocked_from_cookie(raw_cookie: str | None) -> bool:
    if not raw_cookie:
        return False

    try:
        payload = jwt.decode(
            raw_cookie,
            _get_lock_secret(),
            algorithms=[os.getenv("JWT_ALGORITHM", "HS256")],
            options={"require_exp": True},
        )
    except JWTError:
        return False

    if payload.get("sub") != _LOCK_SUBJECT:
        return False
    if payload.get("typ") != _LOCK_TOKEN_TYPE:
        return False

    return True


__all__ = [
    "lock_cookie_name",
    "is_app_lock_enabled",
    "verify_app_lock_password",
    "create_app_lock_token",
    "is_unlocked_from_cookie",
]
