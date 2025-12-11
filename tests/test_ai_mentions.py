"""Integration tests for @SocialSphereAI mentions in posts and comments."""
from __future__ import annotations

import os
from typing import Callable, Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

os.environ.setdefault("DISABLE_CLEANUP", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./test_ai_mentions.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Post, PostComment, User  # noqa: E402
from app.services import get_current_user  # noqa: E402
from app.services.ai_mention_service import set_ai_mention_llm_client  # noqa: E402
from app.services.chatbot_service import ChatCompletionResult, LLMClient  # noqa: E402


class StubLLM(LLMClient):
    def __init__(self, content: str = "Hi from AI") -> None:
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
        session.execute(delete(PostComment))
        session.execute(delete(Post))
        session.execute(delete(User))
        session.commit()
    yield


@pytest.fixture(autouse=True)
def stub_llm() -> Iterator[StubLLM]:
    client = StubLLM()
    set_ai_mention_llm_client(client)
    yield client
    set_ai_mention_llm_client(None)


@pytest.fixture
def authed_client() -> Iterator[Callable[[User], TestClient]]:
    with TestClient(app) as client:
        def _with_user(user: User) -> TestClient:
            app.dependency_overrides[get_current_user] = lambda: user
            return client
        yield _with_user
    app.dependency_overrides.clear()


def test_ai_replies_to_comment_mention(authed_client, stub_llm: StubLLM):
    stub_llm.content = "Hey there!"
    with SessionLocal() as session:
        author = User(username="writer", hashed_password="pw")
        session.add(author)
        session.commit()
        session.refresh(author)
        post = Post(user_id=author.id, caption="Regular update")
        session.add(post)
        session.commit()
        session.refresh(post)

    client = authed_client(author)
    response = client.post(f"/posts/{post.id}/comments", json={"content": "Hi @SocialSphereAI, how are you?"})
    assert response.status_code == 201
    assert stub_llm.calls == 1

    with SessionLocal() as session:
        comments = session.query(PostComment).filter(PostComment.post_id == post.id).order_by(PostComment.created_at.asc()).all()
        assert len(comments) == 2  # user + AI
        user_comment, ai_comment = comments
        bot_user = session.get(User, ai_comment.user_id)
        assert bot_user is not None
        assert str(bot_user.username) == "SocialSphereAI"
        assert ai_comment.parent_id == user_comment.id
        assert ai_comment.content == "Hey there!"


def test_ai_replies_to_post_mention(authed_client, stub_llm: StubLLM):
    stub_llm.content = "I can help with that!"
    with SessionLocal() as session:
        author = User(username="posty", hashed_password="pw")
        session.add(author)
        session.commit()
        session.refresh(author)

    client = authed_client(author)
    response = client.post("/posts", data={"caption": "@SocialSphereAI share some news"})
    assert response.status_code == 201
    body = response.json()
    post_id = UUID(body["id"])
    assert stub_llm.calls == 1

    with SessionLocal() as session:
        comments = session.query(PostComment).filter(PostComment.post_id == post_id).all()
        assert len(comments) == 1
        bot_comment = comments[0]
        bot_user = session.get(User, bot_comment.user_id)
        assert bot_user is not None
        assert str(bot_user.username) == "SocialSphereAI"
        assert bot_comment.parent_id is None
        assert bot_comment.content == "I can help with that!"
