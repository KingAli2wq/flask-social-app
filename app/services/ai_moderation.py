"""AI-based text moderation helpers.

This module provides an optional LLM-driven moderation layer for user-supplied text.
It is designed to work with Ollama (local or cloud) via the /api/chat endpoint.

Notes:
- This does not replace authentication/authorization.
- This is best-effort: if the AI moderation call fails, callers should fall back
  to existing rule-based checks.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

import httpx

from .feature_flags import get_ai_text_moderation_state

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AiModerationDecision:
    allowed: bool
    violations: tuple[str, ...] = ()
    reason: str = ""
    confidence: float | None = None


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_ai_text_moderation_enabled() -> bool:
    # Keep tests hermetic unless explicitly enabled.
    if os.getenv("PYTEST_CURRENT_TEST") is not None and not _is_truthy(os.getenv("AI_TEXT_MODERATION_ALLOW_IN_TESTS")):
        return False
    return bool(get_ai_text_moderation_state().enabled)


def _ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")


def _ollama_model() -> str:
    # Prefer a dedicated moderation model, else reuse the primary model.
    return os.getenv(
        "OLLAMA_MODERATION_MODEL",
        os.getenv("OLLAMA_MODEL", os.getenv("LOCAL_LLM_MODEL", "gpt-oss:120b-cloud")),
    )


def _is_cloud_host(base_url: str) -> bool:
    token = base_url.lower()
    return "ollama.com" in token


def _ollama_headers() -> dict[str, str]:
    base_url = _ollama_base_url()
    if not _is_cloud_host(base_url):
        return {}

    api_key = os.getenv("OLLAMA_API_KEY")
    if not api_key:
        # Avoid crashing user actions; treat as a failure and let callers fall back.
        logger.warning("AI moderation enabled but OLLAMA_API_KEY is not set for cloud usage")
        return {}

    return {"Authorization": f"Bearer {api_key}"}


def get_ai_text_moderation_provider_info() -> dict[str, object]:
    """Return safe-to-display info about the moderation model/provider.

    This intentionally does not expose any API keys.
    """

    base_url = _ollama_base_url()
    cloud = _is_cloud_host(base_url)
    return {
        "base_url": base_url,
        "model": _ollama_model(),
        "cloud": cloud,
        "auth_configured": bool(os.getenv("OLLAMA_API_KEY")) if cloud else None,
    }


def _timeout() -> httpx.Timeout:
    # Reuse Ollama-ish timeouts. Moderation should be fast, but cloud may be slower.
    connect = float(os.getenv("AI_TEXT_MODERATION_CONNECT_TIMEOUT", os.getenv("OLLAMA_TIMEOUT", "20")))
    read = float(os.getenv("AI_TEXT_MODERATION_READ_TIMEOUT", os.getenv("OLLAMA_STREAM_TIMEOUT", "40")))
    write = float(os.getenv("AI_TEXT_MODERATION_WRITE_TIMEOUT", os.getenv("OLLAMA_TIMEOUT", "20")))
    pool = float(os.getenv("AI_TEXT_MODERATION_POOL_TIMEOUT", os.getenv("OLLAMA_TIMEOUT", "20")))
    return httpx.Timeout(connect=max(5.0, connect), read=max(5.0, read), write=max(5.0, write), pool=max(5.0, pool))


def moderate_text(
    text: str,
    *,
    field_name: str = "content",
    allow_adult_nsfw: bool = False,
) -> AiModerationDecision | None:
    """Return an AI moderation decision for user-supplied text.

    Returns None on any failure so callers can fall back to local checks.
    """

    if not is_ai_text_moderation_enabled():
        return None

    normalized = (text or "").strip()
    if not normalized:
        return AiModerationDecision(allowed=True, violations=(), reason="")

    system = (
        "You are a content moderation classifier for a social media app. "
        "Given user-supplied text, determine if it should be allowed. "
        "Return ONLY valid JSON with this schema: "
        "{\"allowed\": boolean, \"violations\": string[], \"reason\": string, \"confidence\": number}. "
        "Violations should be short category tokens like: minors, harassment, self_harm, illegal, doxxing, spam. "
        "Profanity/swearing/vulgar language by itself is allowed; do NOT block content just for profanity. "
        "Only use 'harassment' when the text targets a person or group with abusive, threatening, or degrading language. "
        "If the text is allowed, return allowed=true and an empty violations array. "
        "Be strict about minors and exploitation content. "
        "Minors content is NEVER allowed. If the text sexualizes or involves minors/underage people, set allowed=false and include violation 'minors'. "
        "If allow_adult_nsfw is true, adult sexual content (including explicit NSFW and sexual propositions directed at another person) may be allowed, "
        "as long as it does not involve minors, underage themes, or anything indicating an age below 18."
    )

    user = {
        "field": field_name,
        "allow_adult_nsfw": bool(allow_adult_nsfw),
        "text": normalized,
    }

    payload = {
        "model": _ollama_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        "stream": False,
        "keep_alive": int(os.getenv("AI_TEXT_MODERATION_KEEP_ALIVE_SECONDS", "0")),
        # Many Ollama models honor this to force JSON output.
        "format": "json",
    }

    base_url = _ollama_base_url()
    url = f"{base_url}/api/chat"

    try:
        with httpx.Client(timeout=_timeout(), headers=_ollama_headers() or None) as client:
            response = client.post(url, json=payload)
    except httpx.HTTPError:
        logger.exception("AI moderation request failed")
        return None

    if response.status_code >= 400:
        logger.warning("AI moderation returned %s: %s", response.status_code, response.text[:200])
        return None

    try:
        data = response.json()
    except ValueError:
        logger.warning("AI moderation returned non-JSON response")
        return None

    message = data.get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        logger.warning("AI moderation response missing content")
        return None

    try:
        verdict = json.loads(content)
    except ValueError:
        logger.warning("AI moderation content was not valid JSON")
        return None

    allowed = bool(verdict.get("allowed"))
    raw_violations = verdict.get("violations", [])
    if isinstance(raw_violations, str):
        violations = (raw_violations.strip(),) if raw_violations.strip() else ()
    elif isinstance(raw_violations, list):
        violations = tuple(str(item).strip() for item in raw_violations if str(item).strip())
    else:
        violations = ()

    reason = str(verdict.get("reason") or "").strip()

    confidence_value = verdict.get("confidence")
    confidence: float | None
    try:
        confidence = float(confidence_value) if confidence_value is not None else None
    except (TypeError, ValueError):
        confidence = None

    return AiModerationDecision(
        allowed=allowed,
        violations=violations,
        reason=reason,
        confidence=confidence,
    )


__all__ = [
    "AiModerationDecision",
    "get_ai_text_moderation_provider_info",
    "is_ai_text_moderation_enabled",
    "moderate_text",
]
