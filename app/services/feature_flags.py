"""Runtime feature flags with DB-backed overrides.

We keep an in-memory cache for fast checks in hot paths (e.g., moderation).
Admins can update flags via API which persists to DB and updates the cache.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import AppSetting


AI_TEXT_MODERATION_FLAG_KEY = "feature_flag.ai_text_moderation_enabled"


@dataclass(frozen=True)
class BoolFlagState:
    enabled: bool
    source: str  # "db" | "env" | "default"


_FLAG_CACHE: dict[str, bool] = {}


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_feature_flags(db: Session) -> None:
    """Load known flags from DB into memory."""

    try:
        rows = db.scalars(select(AppSetting).where(AppSetting.key.in_([AI_TEXT_MODERATION_FLAG_KEY]))).all()
    except SQLAlchemyError:
        # Best-effort: app should still boot with env/default values.
        return

    for row in rows:
        if row is None:
            continue
        key = getattr(row, "key", None)
        value = getattr(row, "value", None)
        if not key:
            continue
        if value is None:
            _FLAG_CACHE.pop(key, None)
            continue
        _FLAG_CACHE[key] = _is_truthy(str(value))


def get_flag_override(key: str) -> bool | None:
    return _FLAG_CACHE.get(key)


def set_flag_override(db: Session, key: str, enabled: bool) -> BoolFlagState:
    """Persist and cache a boolean feature flag."""

    normalized = bool(enabled)
    instance = db.get(AppSetting, key)
    if instance is None:
        instance = AppSetting(key=key, value="true" if normalized else "false")
        db.add(instance)
    else:
        instance.value = "true" if normalized else "false"

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise exc

    _FLAG_CACHE[key] = normalized
    return BoolFlagState(enabled=normalized, source="db")


def get_ai_text_moderation_state() -> BoolFlagState:
    """Return effective AI moderation enabled state + where it came from."""

    override = get_flag_override(AI_TEXT_MODERATION_FLAG_KEY)
    if override is not None:
        return BoolFlagState(enabled=override, source="db")

    if _is_truthy(os.getenv("AI_TEXT_MODERATION_ENABLED")):
        return BoolFlagState(enabled=True, source="env")

    return BoolFlagState(enabled=False, source="default")


__all__ = [
    "AI_TEXT_MODERATION_FLAG_KEY",
    "BoolFlagState",
    "load_feature_flags",
    "get_flag_override",
    "set_flag_override",
    "get_ai_text_moderation_state",
]
