"""Utilities for loading sensitive configuration without leaking values."""
from __future__ import annotations

import os
from typing import Final

__all__ = ["MissingSecretError", "require_secret", "is_placeholder"]


class MissingSecretError(RuntimeError):
    """Raised when a required secret environment variable is not set."""


_PLACEHOLDER_VALUES: Final[set[str]] = {
    "changeme",
    "change-me",
    "placeholder",
    "example",
    "sample",
    "your-key-here",
}


def is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    normalized = value.strip().lower()
    return not normalized or normalized in _PLACEHOLDER_VALUES


def require_secret(name: str) -> str:
    """Return a trimmed secret value or raise :class:`MissingSecretError`."""

    value = os.getenv(name)
    if is_placeholder(value):
        raise MissingSecretError(f"Environment variable {name} is required and must not use placeholder defaults")
    return value.strip()
