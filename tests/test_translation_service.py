import logging

import pytest

from app.services import translation_service as ts


def _clear_translation_caches() -> None:
    ts._warn_missing_dependency.cache_clear()
    ts._get_translator.cache_clear()
    ts._translate_cached.cache_clear()


def test_translate_text_noops_when_dependency_missing(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    _clear_translation_caches()

    monkeypatch.setattr(ts, "_HAS_EASYGOOGLETRANSLATE", False, raising=False)

    caplog.set_level(logging.WARNING)
    text = "Hello world"

    assert ts.translate_text(text, "fa") == text

    # Warn once via lru_cache
    assert "Translation disabled: easygoogletranslate is not installed" in caplog.text

    caplog.clear()
    assert ts.translate_text(text, "fa") == text
    assert "Translation disabled: easygoogletranslate is not installed" not in caplog.text


def test_translate_text_returns_original_on_translation_error(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    _clear_translation_caches()

    monkeypatch.setattr(ts, "_HAS_EASYGOOGLETRANSLATE", True, raising=False)

    def boom(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("translator down")

    monkeypatch.setattr(ts, "_translate_cached", boom)

    caplog.set_level(logging.ERROR)
    text = "Hello"

    assert ts.translate_text(text, "fr-CA") == text
    assert "Translation failed" in caplog.text
