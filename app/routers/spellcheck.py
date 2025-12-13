"""Spell-check endpoint for lightweight suggestions."""
from __future__ import annotations

import re
from typing import Iterable

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from spellchecker import SpellChecker

router = APIRouter(prefix="/spellcheck", tags=["spellcheck"])

_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z']*")
_MAX_TEXT_LENGTH = 4000
_spellchecker = SpellChecker(distance=1)
_MIN_WORD_LENGTH = 3


class SpellcheckRequest(BaseModel):
    text: str = Field("", description="Raw text to check for spelling issues")


class Misspelling(BaseModel):
    start: int = Field(..., ge=0, description="Inclusive start offset of the misspelt token")
    end: int = Field(..., ge=0, description="Exclusive end offset of the misspelt token")
    word: str = Field(..., description="Token as provided by the client")
    suggestions: list[str] = Field(default_factory=list, description="Replacement suggestions ordered by likelihood")


class SpellcheckResponse(BaseModel):
    text: str
    misspellings: list[Misspelling]


def _extract_tokens(text: str) -> Iterable[tuple[str, int, int]]:
    for match in _WORD_PATTERN.finditer(text):
        token = match.group(0)
        yield token, match.start(), match.end()


def _safe_float(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (float, int, str)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _should_check(token: str) -> bool:
    if len(token) < _MIN_WORD_LENGTH:
        return False
    if any(char.isdigit() for char in token):
        return False
    return True


def _build_suggestions(word: str) -> list[str]:
    candidates = list(_spellchecker.candidates(word) or [])
    score_fn = getattr(_spellchecker, "word_probability", None)
    scored = []
    for candidate in candidates:
        if candidate == word:
            continue
        score = 0.0
        if callable(score_fn):
            try:
                score = _safe_float(score_fn(candidate))
            except (TypeError, ValueError):
                score = 0.0
        else:
            freq_store = getattr(_spellchecker, "word_frequency", None)
            if freq_store is not None:
                freq_lookup = getattr(freq_store, "frequency", None)
                total_lookup = getattr(freq_store, "N", None)
                try:
                    freq = _safe_float(freq_lookup(candidate)) if callable(freq_lookup) else 0.0
                    total = _safe_float(total_lookup) if total_lookup is not None else 0.0
                    score = (freq / total) if total else 0.0
                except (TypeError, ValueError, ZeroDivisionError):
                    score = 0.0
        scored.append((score, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    ordered = [candidate for _, candidate in scored]
    # Fallback to the library's best correction if scoring produced nothing.
    if not ordered:
        primary = _spellchecker.correction(word)
        if primary and primary != word:
            ordered.append(primary)
    return ordered[:3]


@router.post("/check", response_model=SpellcheckResponse)
def spellcheck_text(payload: SpellcheckRequest) -> SpellcheckResponse:
    text = payload.text or ""
    if len(text) > _MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Text must be {_MAX_TEXT_LENGTH} characters or fewer",
        )

    tokens = list(_extract_tokens(text))
    filtered_tokens = [(token, start, end) for token, start, end in tokens if _should_check(token)]
    lower_tokens = [token.lower() for token, _, _ in filtered_tokens]
    misspelt = _spellchecker.unknown(lower_tokens)

    misspellings: list[Misspelling] = []
    for (token, start, end), lower in zip(filtered_tokens, lower_tokens):
        if lower not in misspelt:
            continue
        misspellings.append(
            Misspelling(
                start=start,
                end=end,
                word=token,
                suggestions=_build_suggestions(lower),
            )
        )

    return SpellcheckResponse(text=text, misspellings=misspellings)


__all__ = ["router"]
