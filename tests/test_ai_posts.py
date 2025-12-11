"""Tests for the AI-generated post endpoint."""
from __future__ import annotations

import os
from typing import Callable, Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

os.environ.setdefault("DISABLE_CLEANUP", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./test_ai_posts.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Post, User  # noqa: E402
from app.services import get_current_user  # noqa: E402
from app.services.ai_content_service import set_ai_content_llm_client  # noqa: E402
from app.services.chatbot_service import ChatCompletionResult, LLMClient  # noqa: E402


class StubLLM(LLMClient):
    def __init__(self, content: str = "AI hello") -> None:
        self.calls = 0
        self.content = content
        self.last_messages = None

    def complete(self, *, messages, temperature: float = 0.2, allow_policy_override: bool = False):  # type: ignore[override]
        self.calls += 1
        self.last_messages = messages
        return ChatCompletionResult(content=self.content, prompt_tokens=1, completion_tokens=1, model="stub-model")


@pytest.fixture(scope="module", autouse=True)
def _create_schema() -> Iterator[None]:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_database() -> Iterator[None]:
    with SessionLocal() as session:
        session.execute(delete(Post))
        session.execute(delete(User))
        session.commit()
    yield


@pytest.fixture(autouse=True)
def stub_llm() -> Iterator[StubLLM]:
    client = StubLLM()
    set_ai_content_llm_client(client)
    yield client
    set_ai_content_llm_client(None)


@pytest.fixture
def authed_client() -> Iterator[Callable[[User], TestClient]]:
    with TestClient(app) as client:
        def _with_user(user: User) -> TestClient:
            app.dependency_overrides[get_current_user] = lambda: user
            return client
        yield _with_user
    app.dependency_overrides.clear()


def test_generate_post_creates_bot_post(authed_client, stub_llm: StubLLM):
    stub_llm.content = "Fresh vibes for everyone"
    with SessionLocal() as session:
        author = User(username="poster", hashed_password="pw")
        admin = User(username="owner", hashed_password="pw", role="owner")
        session.add_all([author, admin])
        session.commit()
        session.refresh(author)
        session.refresh(admin)
        session.add(Post(user_id=author.id, caption="Checking in with the crew"))
        session.commit()

    client = authed_client(admin)
    response = client.post("/ai/generate-post", json={"max_context_posts": 5, "lookback_hours": 48})
    assert response.status_code == 201
    body = response.json()
    assert body["caption"] == "Fresh vibes for everyone"
    assert stub_llm.calls == 1

    stored_id = UUID(body["id"])
    with SessionLocal() as session:
        stored_post = session.get(Post, stored_id)
        assert stored_post is not None
        bot_user = session.get(User, stored_post.user_id)
        assert bot_user is not None
        assert str(bot_user.username) == "SocialSphereAI"


def test_generate_post_requires_admin_role(authed_client):
    with SessionLocal() as session:
        user = User(username="standard", hashed_password="pw", role="user")
        session.add(user)
        session.commit()
        session.refresh(user)

    client = authed_client(user)
    response = client.post("/ai/generate-post")
    assert response.status_code == 403
