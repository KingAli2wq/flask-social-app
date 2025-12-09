import pytest
from fastapi import HTTPException

from app.services.safety import check_content_policy, enforce_safe_text, SafetyViolation


def test_check_content_policy_allows_clean_text():
    result = check_content_policy("Let's plan a picnic by the lake tomorrow.")
    assert result.allowed is True
    assert result.violations == []


@pytest.mark.parametrize(
    "text, expected_violation",
    [
        ("This story features an underage child.", SafetyViolation.MINORS),
        ("Send me nude pics please.", SafetyViolation.SEXUAL),
        ("OnlyFans links allowed?", SafetyViolation.NSFW),
        ("Those inferior race members...", SafetyViolation.HATE),
        ("Go die you idiot", SafetyViolation.HARASSMENT),
        ("Let's stab everyone there", SafetyViolation.VIOLENCE),
    ],
)
def test_check_content_policy_blocks_abusive_text(text, expected_violation):
    result = check_content_policy(text)
    assert result.allowed is False
    assert expected_violation in result.violations


def test_enforce_safe_text_raises_for_blocked_content():
    with pytest.raises(HTTPException) as exc:
        enforce_safe_text("Send nudes please", field_name="message")
    assert exc.value.status_code == 422
    assert any(
        violation in exc.value.detail.get("violations", [])
        for violation in [SafetyViolation.SEXUAL.value, SafetyViolation.NSFW.value]
    )


def test_enforce_safe_text_passes_for_safe_content():
    # Should not raise
    enforce_safe_text("Thanks for the update!", field_name="message")
