"""Tests for the Hugging Face powered emotion detection service and system endpoint."""
from __future__ import annotations

import os
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

# Ensure FastAPI initialises against a dedicated sqlite database when running these tests.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./test_emotions.db")
os.environ.setdefault("JWT_SECRET_KEY", "emotion-test-secret")
os.environ.setdefault("DISABLE_CLEANUP", "true")

from app.main import app  # noqa: E402
from app.services.emotion_service import detect_emotions  # noqa: E402


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """Provide a reusable FastAPI test client."""

    with TestClient(app) as test_client:
        yield test_client


def test_detect_emotions_returns_ranked_predictions() -> None:
    predictions = detect_emotions("I am so happy and optimistic today!", top_k=4, min_score=0.05)

    assert predictions, "Expected at least one emotion prediction"
    assert len(predictions) <= 4
    assert all(0.0 <= item.score <= 1.0 for item in predictions)
    assert all(current.score >= next_item.score for current, next_item in zip(predictions, predictions[1:]))


def test_detect_emotions_handles_blank_text() -> None:
    assert detect_emotions("   ") == []


def test_system_test_emotions_endpoint(client: TestClient) -> None:
    payload = {"text": "I feel anxious but hopeful.", "top_k": 3}

    response = client.post("/system/test-emotions", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["text"] == payload["text"].strip()
    assert "predictions" in data
    assert isinstance(data["predictions"], list)
    if data["predictions"]:
        first = data["predictions"][0]
        assert {"label", "score"}.issubset(first)
    # Directive is optional but when provided should be a string.
    directive = data.get("directive")
    if directive is not None:
        assert isinstance(directive, str)
