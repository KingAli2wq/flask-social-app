"""Lightweight translation service built on easygoogletranslate with caching."""
from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from typing import Any, Literal, cast

EasyGoogleTranslate: Any

try:
    from easygoogletranslate import EasyGoogleTranslate as _EasyGoogleTranslateImpl
except ImportError:  # pragma: no cover - optional runtime dependency
    _EasyGoogleTranslateImpl = None

if _EasyGoogleTranslateImpl is None:
    class _FallbackEasyGoogleTranslate:  # type: ignore[misc]
        def __init__(self, *_, **__):
            raise ImportError("easygoogletranslate is not installed; add it to your environment")

    EasyGoogleTranslate = _FallbackEasyGoogleTranslate
else:
    EasyGoogleTranslate = _EasyGoogleTranslateImpl


logger = logging.getLogger(__name__)

SupportedLang = Literal["zh-CN", "fr-CA", "fa"]
DEFAULT_LANGUAGE = "en"

_TRANSLATOR: Any = EasyGoogleTranslate(
    source_language="auto",
    target_language="en",
    timeout=10,
)

_LANGUAGE_NAMES: dict[SupportedLang, str] = {
    "zh-CN": "Chinese (China)",
    "fr-CA": "French (Canada)",
    "fa": "Persian",
}


def supported_languages() -> dict[str, str]:
    """Return mapping of language code to display name."""

    return {code: name for code, name in _LANGUAGE_NAMES.items()}


def normalize_language_preference(preference: str | None) -> str:
    """Normalize a stored language preference, defaulting to English."""

    if preference is None:
        return DEFAULT_LANGUAGE
    normalized = preference.strip()
    if not normalized:
        return DEFAULT_LANGUAGE
    if normalized.lower() == DEFAULT_LANGUAGE:
        return DEFAULT_LANGUAGE
    if normalized in _LANGUAGE_NAMES:
        return normalized
    raise ValueError(f"Unsupported language: {preference}")


def resolve_target_language(preference: str | None) -> SupportedLang | None:
    normalized = normalize_language_preference(preference)
    if normalized == DEFAULT_LANGUAGE:
        return None
    return cast(SupportedLang, normalized)


def _cache_key(text: str, target_language: str) -> str:
    digest = hashlib.sha256()
    digest.update(target_language.encode("utf-8", "ignore"))
    digest.update(b"|")
    digest.update(text.encode("utf-8", "ignore"))
    return digest.hexdigest()


@lru_cache(maxsize=1024)
def _translate_cached(text: str, target_language: str) -> str:
    translator: Any = EasyGoogleTranslate(source_language="auto", target_language=target_language, timeout=10)
    return translator.translate(text)


def translate_text(text: str, target_language: SupportedLang) -> str:
    if not text:
        return ""
    if target_language not in _LANGUAGE_NAMES:
        raise ValueError(f"Unsupported language: {target_language}")
    try:
        return _translate_cached(text, target_language)
    except Exception:  # pragma: no cover - external service
        logger.exception("Translation failed")
        return text


def translate_batch(texts: list[str], target_language: SupportedLang) -> list[str]:
    results: list[str] = []
    for text in texts:
        results.append(translate_text(text, target_language))
    return results

__all__ = [
    "translate_text",
    "translate_batch",
    "supported_languages",
    "SupportedLang",
    "DEFAULT_LANGUAGE",
    "normalize_language_preference",
    "resolve_target_language",
]
