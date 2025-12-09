"""Lightweight, rule-based moderation helpers for Social AI prompts."""
from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel


class SafetyViolation(str, Enum):
    MINORS = "minors"
    NON_CONSENT = "non_consent"
    EXTREME_SEXUAL = "extreme_sexual"
    SELF_HARM = "self_harm"
    VIOLENCE = "violence"
    CRIME_TERROR = "crime_terror"
    HATE = "hate"
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
_NON_CONSENT_KEYWORDS = [
    "rape",
    "raped",
    "non-consensual",
    "nonconsensual",
    "force her",
    "force him",
    "forced",
    "drug her",
    "drug him",
    "sleeping girl",
]
_SELF_HARM_KEYWORDS = [
    "kill myself",
    "kill me",
    "suicide",
    "end my life",
    "end it all",
    "cut myself",
    "self harm",
]
_VIOLENCE_KEYWORDS = [
    "torture",
    "behead",
    "dismember",
    "maim",
    "stab",
    "shoot",
]
_CRIME_TERROR_KEYWORDS = [
    "how to make a bomb",
    "build a bomb",
    "explosive",
    "terrorist",
    "mass shooting",
    "assassinate",
]
_HATE_KEYWORDS = [
    "kill all",
    "wipe out",
    "exterminate",
    "dirty",
    "subhuman",
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

    if _match_any(normalized, _NON_CONSENT_KEYWORDS):
        violations.append(SafetyViolation.NON_CONSENT)
        reasons.append("Content references non-consensual acts")

    if _match_any(normalized, _SELF_HARM_KEYWORDS):
        violations.append(SafetyViolation.SELF_HARM)
        reasons.append("Content references self-harm")

    if _match_any(normalized, _VIOLENCE_KEYWORDS):
        violations.append(SafetyViolation.VIOLENCE)
        reasons.append("Content promotes severe violence")

    if _match_any(normalized, _CRIME_TERROR_KEYWORDS):
        violations.append(SafetyViolation.CRIME_TERROR)
        reasons.append("Content promotes crime or terrorism")

    if _match_any(normalized, _HATE_KEYWORDS):
        violations.append(SafetyViolation.HATE)
        reasons.append("Content targets protected groups")

    sexual_hit = _match_any(normalized, _SEXUAL_KEYWORDS)
    if sexual_hit and not allow_adult_nsfw:
        violations.append(SafetyViolation.EXTREME_SEXUAL)
        reasons.append("Explicit sexual content is disabled")

    # Even when adult NSFW is enabled, still block if combined with other high-risk categories.
    if sexual_hit and allow_adult_nsfw:
        if SafetyViolation.MINORS in violations or SafetyViolation.NON_CONSENT in violations:
            if SafetyViolation.EXTREME_SEXUAL not in violations:
                violations.append(SafetyViolation.EXTREME_SEXUAL)
                reasons.append("Sexual content combined with disallowed themes")

    allowed = len(violations) == 0

    # TODO: Emit anonymized telemetry when violations occur to monitor abuse trends.
    return SafetyResult(allowed=allowed, violations=violations, reason="; ".join(reasons))


__all__ = [
    "SafetyViolation",
    "SafetyResult",
    "check_content_policy",
]
