"""Lightweight, rule-based moderation helpers for Social AI prompts."""
from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any, List, Tuple

from fastapi import HTTPException, status
from pydantic import BaseModel

try:  # pragma: no cover - optional dependency
    from profanity_filter import ProfanityFilter
except ImportError:  # pragma: no cover - optional dependency
    ProfanityFilter = None  # type: ignore[misc, assignment]

try:  # pragma: no cover - optional dependency
    from hatesonar import Sonar
except ImportError:  # pragma: no cover - optional dependency
    Sonar = None  # type: ignore[misc, assignment]


logger = logging.getLogger(__name__)


class SafetyViolation(str, Enum):
    MINORS = "minors"
    SEXUAL = "sexual"
    NSFW = "nsfw"
    HATE = "hate"
    HARASSMENT = "harassment"
    VIOLENCE = "violence"
    PROFANITY = "profanity"
    TOXICITY = "toxicity"


class SafetyResult(BaseModel):
    allowed: bool
    violations: List[SafetyViolation] = []
    reason: str = ""


_LEETSPEAK_TABLE = str.maketrans(
    {
        "0": "o",
        "1": "i",
        "2": "z",
        "3": "e",
        "4": "a",
        "5": "s",
        "6": "g",
        "7": "t",
        "8": "b",
        "9": "g",
        "$": "s",
        "@": "a",
        "!": "i",
        "|": "i",
    }
)
_COMPACT_RE = re.compile(r"[^a-z0-9]+")


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
    "bitch",
    "trash",
    "moron",
    "dumb",
    "jerk",
]


_pf_instance: Any | None = None
_sonar_instance: Any | None = None
_HATESONAR_CONFIDENCE_THRESHOLD = 0.6

_VIOLENCE_KEYWORDS = [
    "murder",
    "blood",
    "stab",
    "shoot",
    "choke",
]


def _build_token(points: tuple[int, ...]) -> str:
    return "".join(chr(value) for value in points)


_HATE_SLUR_STEMS = [
    _build_token((110, 105, 103, 103)),  # common ethnic slur stem
    _build_token((102, 97, 103, 103)),
    _build_token((115, 112, 105, 99)),
    _build_token((107, 105, 107, 101)),
    _build_token((99, 104, 105, 110, 107)),
    _build_token((103, 111, 111, 107)),
    _build_token((119, 101, 116, 98)),
    _build_token((116, 114, 97, 110, 110)),
    _build_token((99, 111, 111, 110)),
]


def _strip_non_alnum(value: str) -> str:
    return _COMPACT_RE.sub("", value)


def _normalize_variants(text: str) -> tuple[str, str]:
    collapsed = text.translate(_LEETSPEAK_TABLE)
    squashed = _strip_non_alnum(collapsed)
    return collapsed, squashed


def _contains_keyword_variants(collapsed: str, squashed: str, keywords: list[str]) -> bool:
    for keyword in keywords:
        normalized_keyword = (keyword or "").lower().strip()
        if not normalized_keyword:
            continue
        compact = _strip_non_alnum(normalized_keyword)
        if normalized_keyword in collapsed:
            return True
        if compact and compact in squashed:
            return True
    return False


def _get_profanity_filter() -> Any | None:
    global _pf_instance
    if _pf_instance is not None:
        return _pf_instance
    if ProfanityFilter is None:
        return None
    try:
        _pf_instance = ProfanityFilter()
    except Exception:  # pragma: no cover - defensive guard
        logger.exception("Failed to initialize ProfanityFilter")
        _pf_instance = None
    return _pf_instance


def _get_hatesonar() -> Any | None:
    global _sonar_instance
    if _sonar_instance is not None:
        return _sonar_instance
    if Sonar is None:
        return None
    try:
        _sonar_instance = Sonar()
    except Exception:  # pragma: no cover - defensive guard
        logger.exception("Failed to initialize HateSonar classifier")
        _sonar_instance = None
    return _sonar_instance


def _detect_with_profanity_filter(text: str) -> bool:
    detector = _get_profanity_filter()
    if detector is None or not text.strip():
        return False
    try:
        return bool(detector.is_profane(text))
    except Exception:  # pragma: no cover - defensive guard
        logger.exception("ProfanityFilter failed to evaluate input")
        return False


def _detect_with_hatesonar(text: str) -> Tuple[str, float] | None:
    classifier = _get_hatesonar()
    if classifier is None or not text.strip():
        return None
    try:
        result = classifier.ping(text=text)
    except Exception:  # pragma: no cover - defensive guard
        logger.exception("HateSonar failed to evaluate input")
        return None
    top_class = result.get("top_class")
    if not isinstance(top_class, str):
        return None
    confidence = 0.0
    for entry in result.get("classes", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("class_name") == top_class:
            try:
                confidence = float(entry.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
            break
    if confidence < _HATESONAR_CONFIDENCE_THRESHOLD:
        return None
    return top_class, confidence


def check_content_policy(text: str, allow_adult_nsfw: bool = False) -> SafetyResult:
    """Basic keyword-based moderation for all user-supplied text."""

    normalized = (text or "").lower()
    if not normalized.strip():
        return SafetyResult(allowed=True, violations=[], reason="")

    collapsed, squashed = _normalize_variants(normalized)

    violations: list[SafetyViolation] = []
    reasons: list[str] = []

    if _detect_with_profanity_filter(text):
        violations.append(SafetyViolation.PROFANITY)
        reasons.append("Profanity detected by lexical filter")

    if _contains_keyword_variants(collapsed, squashed, _MINOR_KEYWORDS):
        violations.append(SafetyViolation.MINORS)
        reasons.append("Content references minors")

    if not allow_adult_nsfw and _contains_keyword_variants(collapsed, squashed, _SEXUAL_KEYWORDS):
        violations.append(SafetyViolation.SEXUAL)
        reasons.append("Sexual content is not allowed")

    if not allow_adult_nsfw and _contains_keyword_variants(collapsed, squashed, _NSFW_KEYWORDS):
        violations.append(SafetyViolation.NSFW)
        reasons.append("NSFW content is blocked")

    hate_detected = _contains_keyword_variants(collapsed, squashed, _HATE_PARTIALS)
    if not hate_detected:
        hate_detected = any(stem and stem in squashed for stem in _HATE_SLUR_STEMS)
    if hate_detected:
        violations.append(SafetyViolation.HATE)
        reasons.append("Hateful or targeting language detected")

    if _contains_keyword_variants(collapsed, squashed, _HARASSMENT_PATTERNS):
        violations.append(SafetyViolation.HARASSMENT)
        reasons.append("Harassing or bullying language detected")

    if _contains_keyword_variants(collapsed, squashed, _VIOLENCE_KEYWORDS):
        violations.append(SafetyViolation.VIOLENCE)
        reasons.append("Graphic violence references detected")

    sonar_signal = _detect_with_hatesonar(text)
    if sonar_signal:
        label, _confidence = sonar_signal
        if label == "hate_speech" and SafetyViolation.HATE not in violations:
            violations.append(SafetyViolation.HATE)
            reasons.append("HateSonar classified the text as hate speech")
        elif label == "offensive_language" and SafetyViolation.TOXICITY not in violations:
            violations.append(SafetyViolation.TOXICITY)
            reasons.append("HateSonar detected offensive language")

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
