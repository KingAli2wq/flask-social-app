import pytest
from fastapi import HTTPException

from app.services.safety import check_content_policy, enforce_safe_text, SafetyViolation


def _build_word(points):
    return "".join(chr(value) for value in points)


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


def test_check_content_policy_detects_leetspeak_profanity():
    result = check_content_policy("F.u.c.k this thread right now")
    assert result.allowed is False
    assert SafetyViolation.SEXUAL in result.violations


def test_check_content_policy_detects_slur_stems():
    slur = _build_word((110, 105, 103, 103, 101, 114))
    result = check_content_policy(f"That {slur} remark isn't tolerated here.")
    assert result.allowed is False
    assert SafetyViolation.HATE in result.violations


def test_check_content_policy_respects_adult_override():
    result = check_content_policy("Posting tasteful nude art", allow_adult_nsfw=True)
    assert result.allowed is True
    assert SafetyViolation.SEXUAL not in result.violations


@pytest.mark.parametrize(
    "text",
    [
        "Stop being such a bitch",
        "You're absolute trash",
        "This moron can't code",
        "What a dumb jerk",
    ],
)
def test_check_content_policy_blocks_common_harassment_terms(text):
    result = check_content_policy(text)
    assert result.allowed is False
    assert SafetyViolation.HARASSMENT in result.violations


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
