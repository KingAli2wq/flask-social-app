import os

import pytest
from fastapi import HTTPException

import app.services.ai_moderation as ai_moderation
from app.services.safety import enforce_safe_text


def test_enforce_safe_text_blocks_when_ai_flags(monkeypatch):
    monkeypatch.setenv("AI_TEXT_MODERATION_ENABLED", "true")
    monkeypatch.setenv("AI_TEXT_MODERATION_ALLOW_IN_TESTS", "true")

    monkeypatch.setattr(
        ai_moderation,
        "moderate_text",
        lambda *args, **kwargs: ai_moderation.AiModerationDecision(
            allowed=False,
            violations=("harassment",),
            reason="Detected harassment",
            confidence=0.9,
        ),
    )

    with pytest.raises(HTTPException) as exc:
        enforce_safe_text("Hello world", field_name="message")

    assert exc.value.status_code == 422
    assert exc.value.detail.get("source") == "ai"
    assert "harassment" in exc.value.detail.get("violations", [])


def test_enforce_safe_text_falls_back_when_ai_disabled(monkeypatch):
    monkeypatch.delenv("AI_TEXT_MODERATION_ENABLED", raising=False)
    monkeypatch.delenv("AI_TEXT_MODERATION_ALLOW_IN_TESTS", raising=False)

    with pytest.raises(HTTPException):
        enforce_safe_text("Go die you idiot", field_name="message")
