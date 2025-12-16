"""Lightweight i18n utilities for server-rendered UI and API bundles."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException, Request, status

SUPPORTED_LOCALES: tuple[str, ...] = ("en", "zh-CN", "fr-CA", "fa")
DEFAULT_LOCALE = "en"
_I18N_DIR = Path(__file__).resolve().parent.parent / "ui" / "i18n"


def _load_messages(locale: str) -> dict[str, str]:
    path = _I18N_DIR / f"{locale}.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing locale bundle: {locale}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=16)
def get_messages(locale: str) -> dict[str, str]:
    normalized = normalize_locale(locale)
    try:
        return _load_messages(normalized)
    except Exception as exc:  # pragma: no cover - IO bound
        if normalized != DEFAULT_LOCALE:
            return get_messages(DEFAULT_LOCALE)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load translations") from exc


def normalize_locale(locale: str | None) -> str:
    if not locale:
        return DEFAULT_LOCALE
    value = locale.strip()
    if value in SUPPORTED_LOCALES:
        return value
    if value.lower().startswith("en"):
        return DEFAULT_LOCALE
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported locale")


def select_locale(candidate: str | None, accept_languages: Iterable[str] | None = None) -> str:
    if candidate:
        try:
            return normalize_locale(candidate)
        except HTTPException:
            pass
    if accept_languages:
        for lang in accept_languages:
            try:
                return normalize_locale(lang)
            except HTTPException:
                continue
    return DEFAULT_LOCALE


def translate(locale: str, key: str, default: str | None = None) -> str:
    messages = get_messages(locale)
    if key in messages:
        return messages[key]
    fallback = get_messages(DEFAULT_LOCALE)
    if key in fallback:
        return fallback[key]
    return default if default is not None else key


def resolve_request_locale(request: Request) -> str:
    """Resolve locale preference from query, cookie, or Accept-Language."""

    query_locale = request.query_params.get("lang")
    cookie_locale = request.cookies.get("ui_locale")
    accept_header = request.headers.get("accept-language", "")
    accept_candidates = []
    if accept_header:
        accept_candidates = [segment.split(";")[0].strip() for segment in accept_header.split(",") if segment]
    return select_locale(query_locale or cookie_locale, accept_candidates)


__all__ = [
    "DEFAULT_LOCALE",
    "SUPPORTED_LOCALES",
    "get_messages",
    "normalize_locale",
    "select_locale",
    "translate",
    "resolve_request_locale",
]
