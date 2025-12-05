"""Utility helpers for encrypting and decrypting group chat payloads."""
from __future__ import annotations

import secrets
from typing import Final

from cryptography.fernet import Fernet, InvalidToken


class GroupEncryptionError(RuntimeError):
    """Raised when group chat payloads cannot be encrypted or decrypted."""


def generate_group_lock_code(length: int = 24) -> str:
    """Return a pseudo-random hexadecimal lock code displayed to end users."""

    return secrets.token_hex(max(8, length))


def generate_group_encryption_key() -> str:
    """Return a url-safe base64 key compatible with ``cryptography.Fernet``."""

    return Fernet.generate_key().decode("utf-8")


def _coerce_key(raw_key: str) -> bytes:
    if not raw_key:
        raise GroupEncryptionError("Missing encryption key")
    key_bytes = raw_key.encode("utf-8")
    try:
        # Validate the key without mutating it.
        Fernet(key_bytes)
    except (ValueError, TypeError) as exc:  # pragma: no cover - defensive guard
        raise GroupEncryptionError("Invalid encryption key format") from exc
    return key_bytes


def encrypt_group_payload(raw_key: str, plaintext: str) -> str:
    """Encrypt ``plaintext`` using the provided ``raw_key``."""

    key_bytes = _coerce_key(raw_key)
    fernet = Fernet(key_bytes)
    token = fernet.encrypt((plaintext or "").encode("utf-8"))
    return token.decode("utf-8")


def decrypt_group_payload(raw_key: str, ciphertext: str) -> str:
    """Decrypt ``ciphertext`` using the provided ``raw_key``."""

    key_bytes = _coerce_key(raw_key)
    fernet = Fernet(key_bytes)
    try:
        payload = fernet.decrypt((ciphertext or "").encode("utf-8"))
    except InvalidToken as exc:
        raise GroupEncryptionError("Unable to decrypt message") from exc
    return payload.decode("utf-8")


__all__: Final = [
    "GroupEncryptionError",
    "generate_group_lock_code",
    "generate_group_encryption_key",
    "encrypt_group_payload",
    "decrypt_group_payload",
]
