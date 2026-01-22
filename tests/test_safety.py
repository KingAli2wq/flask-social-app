import pytest

from app.services.safety import check_content_policy, enforce_safe_text


def test_check_content_policy_allows_clean_text():
    result = check_content_policy("Let's plan a picnic by the lake tomorrow.")
    assert result.allowed is True


def test_enforce_safe_text_fails_open_when_ai_disabled(monkeypatch):
    monkeypatch.delenv("AI_TEXT_MODERATION_ENABLED", raising=False)
    monkeypatch.delenv("AI_TEXT_MODERATION_ALLOW_IN_TESTS", raising=False)

    # AI-only moderation: with AI disabled, we do not block text.
    enforce_safe_text("Go die you idiot", field_name="message")
