"""Shared helpers for encrypting and decrypting media metadata."""
from __future__ import annotations

from ..security.data_vault import DataVaultError, decrypt_text, encrypt_text, is_ciphertext


def protect_media_value(value: str | None) -> str | None:
    """Encrypt sensitive media metadata before persisting it."""

    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if is_ciphertext(normalized):
        return normalized
    return encrypt_text(normalized)


def reveal_media_value(value: str | None) -> str | None:
    """Decrypt media metadata retrieved from persistence."""

    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if is_ciphertext(normalized):
        return decrypt_text(normalized)
    return normalized


def ensure_media_value(value: str | None) -> str:
    """Force decrypted media metadata and raise if missing."""

    plaintext = reveal_media_value(value)
    if not plaintext:
        raise DataVaultError("Media metadata is missing or unreadable")
    return plaintext


__all__ = ["protect_media_value", "reveal_media_value", "ensure_media_value"]
