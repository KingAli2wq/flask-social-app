"""Application-wide helpers for encrypting sensitive fields at rest."""
from __future__ import annotations

import base64
import binascii
import json
import threading
from typing import Any, Final

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from .secrets import MissingSecretError, require_secret


class DataVaultError(RuntimeError):
    """Raised when data cannot be encrypted or decrypted via the vault."""


_PREFIX: Final[str] = "vault.v1:"
_DET_PREFIX: Final[str] = "vault.det.v1:"
_SCHEME_VAULT: Final[str] = "vault.v1"
_ENCODING_JSON: Final[str] = "json"

_vault_lock = threading.Lock()
_vault_instance: Fernet | None = None
_det_cipher: AESSIV | None = None


def _load_master_key() -> str:
    try:
        raw_key = require_secret("DATA_VAULT_MASTER_KEY")
    except MissingSecretError as exc:
        raise DataVaultError(str(exc)) from exc
    _coerce_key(raw_key)  # validation side-effect
    return raw_key


def _master_secret_bytes() -> bytes:
    raw_key = _load_master_key()
    try:
        return base64.urlsafe_b64decode(raw_key.encode("utf-8"))
    except (ValueError, binascii.Error):  # pragma: no cover - defensive
        raise DataVaultError("DATA_VAULT_MASTER_KEY is invalid")


def _coerce_key(raw_key: str) -> bytes:
    if not raw_key:
        raise DataVaultError("DATA_VAULT_MASTER_KEY is required")
    key_bytes = raw_key.encode("utf-8")
    try:
        Fernet(key_bytes)
    except (ValueError, TypeError) as exc:  # pragma: no cover - guard against invalid keys
        raise DataVaultError("DATA_VAULT_MASTER_KEY is invalid") from exc
    return key_bytes


def _get_vault() -> Fernet:
    global _vault_instance
    if _vault_instance is None:
        with _vault_lock:
            if _vault_instance is None:
                key = _coerce_key(_load_master_key())
                _vault_instance = Fernet(key)
    return _vault_instance


def _get_det_cipher() -> AESSIV:
    global _det_cipher
    if _det_cipher is None:
        with _vault_lock:
            if _det_cipher is None:
                secret = _master_secret_bytes()
                hkdf = HKDF(
                    algorithm=hashes.SHA256(),
                    length=64,
                    salt=b"vault-det",
                    info=b"deterministic-aead",
                )
                det_key = hkdf.derive(secret)
                _det_cipher = AESSIV(det_key)
    return _det_cipher


def encrypt_text(value: str) -> str:
    """Encrypt ``value`` and return a prefixed ciphertext safe for storage."""

    if not value:
        value = ""
    if value.startswith(_PREFIX):
        return value
    token = _get_vault().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{_PREFIX}{token}"


def decrypt_text(value: str) -> str:
    """Attempt to decrypt ``value``; passthrough when no vault prefix is set."""

    if not value:
        return ""
    if not value.startswith(_PREFIX):
        return value
    token = value[len(_PREFIX) :]
    try:
        payload = _get_vault().decrypt(token.encode("utf-8"))
    except InvalidToken as exc:
        raise DataVaultError("Unable to decrypt value") from exc
    return payload.decode("utf-8")


def encrypt_bytes(value: bytes) -> bytes:
    """Encrypt raw bytes using the shared Fernet key."""

    if value is None:
        return b""
    return _get_vault().encrypt(value)


def decrypt_bytes(value: bytes) -> bytes:
    """Decrypt bytes produced by :func:`encrypt_bytes`."""

    if not value:
        return b""
    try:
        return _get_vault().decrypt(value)
    except InvalidToken as exc:
        raise DataVaultError("Unable to decrypt binary payload") from exc


def encrypt_text_deterministic(value: str) -> str:
    """Encrypt ``value`` using a deterministic AES-SIV scheme."""

    if value is None:
        return ""
    if value.startswith(_DET_PREFIX):
        return value
    cipher = _get_det_cipher()
    ciphertext = cipher.encrypt(value.encode("utf-8"), associated_data=None)
    token = base64.urlsafe_b64encode(ciphertext).decode("utf-8")
    return f"{_DET_PREFIX}{token}"


def decrypt_text_deterministic(value: str) -> str:
    """Decrypt strings produced by :func:`encrypt_text_deterministic`."""

    if not value:
        return ""
    if value.startswith(_DET_PREFIX):
        token = value[len(_DET_PREFIX) :]
        cipher = _get_det_cipher()
        try:
            payload = cipher.decrypt(base64.urlsafe_b64decode(token.encode("utf-8")), associated_data=None)
        except Exception as exc:  # pragma: no cover - defensive
            raise DataVaultError("Unable to decrypt deterministic value") from exc
        return payload.decode("utf-8")
    if value.startswith(_PREFIX):
        # Allow legacy ciphertexts encrypted with random IVs.
        return decrypt_text(value)
    return value


def encrypt_structured(payload: Any) -> dict[str, Any]:
    """Encrypt an arbitrary JSON-serialisable payload and wrap metadata."""

    blob = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    ciphertext = encrypt_text(blob)
    return {
        "ciphertext": ciphertext,
        "encoding": _ENCODING_JSON,
        "scheme": _SCHEME_VAULT,
        "version": 1,
    }


def decrypt_structured(node: Any) -> Any:
    """Reverse :func:`encrypt_structured` when ciphertext metadata is present."""

    if not isinstance(node, dict) or "ciphertext" not in node:
        return node
    scheme = node.get("scheme")
    encoding = node.get("encoding")
    if scheme != _SCHEME_VAULT or encoding != _ENCODING_JSON:
        return node
    ciphertext = node.get("ciphertext")
    if not isinstance(ciphertext, str):
        return node
    plaintext = decrypt_text(ciphertext)
    return json.loads(plaintext)


def is_ciphertext(value: str | None) -> bool:
    """Return ``True`` when ``value`` appears to be vault ciphertext."""

    return bool(value and value.startswith(_PREFIX))


__all__ = [
    "DataVaultError",
    "decrypt_structured",
    "decrypt_text",
    "encrypt_structured",
    "encrypt_text",
    "is_ciphertext",
]
