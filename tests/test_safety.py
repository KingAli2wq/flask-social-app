import pytest
from fastapi import HTTPException

from app.services.safety import check_content_policy, enforce_safe_text


def test_check_content_policy_allows_clean_text():
    result = check_content_policy("Let's plan a picnic by the lake tomorrow.")
    assert result.allowed is True


def test_enforce_safe_text_fails_open_when_ai_disabled(monkeypatch):
    monkeypatch.delenv("AI_TEXT_MODERATION_ENABLED", raising=False)
    monkeypatch.delenv("AI_TEXT_MODERATION_ALLOW_IN_TESTS", raising=False)

    # AI-only moderation: with AI disabled, we do not block text.
    enforce_safe_text("Go die you idiot", field_name="message")


def test_enforce_safe_text_blocks_minors_even_when_ai_disabled(monkeypatch):
    monkeypatch.delenv("AI_TEXT_MODERATION_ENABLED", raising=False)
    monkeypatch.delenv("AI_TEXT_MODERATION_ALLOW_IN_TESTS", raising=False)

    with pytest.raises(HTTPException) as exc:
        enforce_safe_text("I'm 16yo", field_name="message", allow_adult_nsfw=True)
    assert exc.value.status_code == 422
    assert exc.value.detail.get("source") == "local"
    assert "minors" in (exc.value.detail.get("violations") or [])


def test_enforce_safe_text_allows_adult_nsfw_when_ai_disabled(monkeypatch):
    monkeypatch.delenv("AI_TEXT_MODERATION_ENABLED", raising=False)
    monkeypatch.delenv("AI_TEXT_MODERATION_ALLOW_IN_TESTS", raising=False)

    # Adult sexual content should not be blocked locally (only minors are enforced locally).
    enforce_safe_text("I want you so bad tonight", field_name="message", allow_adult_nsfw=True)
