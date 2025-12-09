"""Lightweight, rule-based moderation helpers for Social AI prompts."""
from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel


class SafetyViolation(str, Enum):
    MINORS = "minors"
    OTHER = "other"


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


def _match_any(text: str, keywords: list[str]) -> bool:
    return any(term in text for term in keywords)


def check_content_policy(text: str, allow_adult_nsfw: bool = False) -> SafetyResult:
    """Basic keyword-based moderation.

    When `allow_adult_nsfw` is False, explicit sexual content is blocked entirely.
    When True, consensual adult content is allowed but high-risk categories remain blocked.
    """

    normalized = (text or "").lower()
    if not normalized.strip():
        return SafetyResult(allowed=True, violations=[], reason="")

    violations: list[SafetyViolation] = []
    reasons: list[str] = []

    if _match_any(normalized, _MINOR_KEYWORDS):
        violations.append(SafetyViolation.MINORS)
        reasons.append("Content references minors")

    allowed = len(violations) == 0

    # TODO: Emit anonymized telemetry when violations occur to monitor abuse trends.
    return SafetyResult(allowed=allowed, violations=violations, reason="; ".join(reasons))


__all__ = [
    "SafetyViolation",
    "SafetyResult",
    "check_content_policy",
]
