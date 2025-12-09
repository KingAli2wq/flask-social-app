"""Lightweight, rule-based moderation helpers for Social AI prompts."""
from __future__ import annotations

from enum import Enum
from typing import List

from fastapi import HTTPException, status
from pydantic import BaseModel


class SafetyViolation(str, Enum):
    MINORS = "minors"
    SEXUAL = "sexual"
    NSFW = "nsfw"
    HATE = "hate"
    HARASSMENT = "harassment"
    VIOLENCE = "violence"


class SafetyResult(BaseModel):
    allowed: bool
    violations: List[SafetyViolation] = []
    reason: str = ""


# TODO: Replace keyword heuristics with an ML-based moderation model when available.
_MINOR_KEYWORDS = [
    "minor",
    "underage",
    "child",
    "children",
    "kid",
    "teen",
    "teenager",
    "loli",
    "young girl",
    "young boy",
    "schoolgirl",
    "school boy",
    "high school",
    "middle school",
    "elementary",
]

_SEXUAL_KEYWORDS = [
    "sex",
    "sexual",
    "fuck",
    "fucking",
    "blowjob",
    "handjob",
    "oral",
    "anal",
    "nsfw",
    "nude",
    "nudes",
    "porn",
]

_NSFW_KEYWORDS = [
    "xxx",
    "camgirl",
    "onlyfans",
    "hardcore",
    "explicit",
]

# Partial strings avoid keeping the exact hateful term in source while still detecting usage.
_HATE_PARTIALS = [
    "nazi",
    "kkk",
    "lynch",
    "gas chamber",
    "inferior race",
    "supremacy",
    "slur",
]

_HARASSMENT_PATTERNS = [
    "kill yourself",
    "go die",
    "you should die",
    "nobody likes you",
    "worthless",
    "loser",
    "idiot",
    "stupid",
    "hate you",
]

_VIOLENCE_KEYWORDS = [
    "murder",
    "blood",
    "stab",
    "shoot",
    "choke",
]


def _match_any(text: str, keywords: list[str]) -> bool:
    return any(term in text for term in keywords)


def check_content_policy(text: str, allow_adult_nsfw: bool = False) -> SafetyResult:
    """Basic keyword-based moderation for all user-supplied text."""

    normalized = (text or "").lower()
    if not normalized.strip():
        return SafetyResult(allowed=True, violations=[], reason="")

    violations: list[SafetyViolation] = []
    reasons: list[str] = []

    if _match_any(normalized, _MINOR_KEYWORDS):
        violations.append(SafetyViolation.MINORS)
        reasons.append("Content references minors")

    if _match_any(normalized, _SEXUAL_KEYWORDS):
        violations.append(SafetyViolation.SEXUAL)
        reasons.append("Sexual content is not allowed")

    if _match_any(normalized, _NSFW_KEYWORDS):
        violations.append(SafetyViolation.NSFW)
        reasons.append("NSFW content is blocked")

    if _match_any(normalized, _HATE_PARTIALS):
        violations.append(SafetyViolation.HATE)
        reasons.append("Hateful or targeting language detected")

    if _match_any(normalized, _HARASSMENT_PATTERNS):
        violations.append(SafetyViolation.HARASSMENT)
        reasons.append("Harassing or bullying language detected")

    if _match_any(normalized, _VIOLENCE_KEYWORDS):
        violations.append(SafetyViolation.VIOLENCE)
        reasons.append("Graphic violence references detected")

    allowed = len(violations) == 0

    # TODO: Emit anonymized telemetry when violations occur to monitor abuse trends.
    return SafetyResult(allowed=allowed, violations=violations, reason="; ".join(reasons))


def enforce_safe_text(
    text: str,
    *,
    allow_adult_nsfw: bool = False,
    field_name: str = "content",
) -> None:
    """Raise an HTTPException when the supplied text violates community guidelines."""

    result = check_content_policy(text, allow_adult_nsfw=allow_adult_nsfw)
    if result.allowed:
        return
    detail = {
        "message": f"{field_name.capitalize()} violates our community guidelines.",
        "violations": [violation.value for violation in result.violations],
        "reason": result.reason,
    }
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


__all__ = [
    "SafetyViolation",
    "SafetyResult",
    "check_content_policy",
    "enforce_safe_text",
]
