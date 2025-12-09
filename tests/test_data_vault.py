"""Unit tests for the data vault helpers."""

from __future__ import annotations

import importlib
import os

from cryptography.fernet import Fernet

from app.security import data_vault


def _reload_data_vault_with_key(key: str) -> None:
    os.environ["DATA_VAULT_MASTER_KEY"] = key
    importlib.reload(data_vault)


def test_encrypt_text_round_trip() -> None:
    key = Fernet.generate_key().decode("utf-8")
    _reload_data_vault_with_key(key)
    plaintext = "hello world"
    ciphertext = data_vault.encrypt_text(plaintext)
    assert ciphertext.startswith("vault.v1:")
    assert data_vault.decrypt_text(ciphertext) == plaintext


def test_encrypt_structured_round_trip() -> None:
    key = Fernet.generate_key().decode("utf-8")
    _reload_data_vault_with_key(key)
    payload = ["https://cdn.example.com/a.jpg", "https://cdn.example.com/b.jpg"]
    wrapped = data_vault.encrypt_structured(payload)
    assert wrapped["scheme"] == "vault.v1"
    assert wrapped["encoding"] == "json"
    assert data_vault.decrypt_structured(wrapped) == payload
