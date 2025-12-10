"""End-to-end tests for the chatbot API with a stubbed LLM client."""
from __future__ import annotations

import os
os.environ.setdefault("DISABLE_CLEANUP", "true")
os.environ.setdefault("DATA_VAULT_MASTER_KEY", os.environ.get("DATA_VAULT_MASTER_KEY", "ZG9udC1zaGlwLXJhaWwtc2VjcmV0LWFpLWtleQ=="))
from typing import AsyncIterator, Callable, Iterator, cast
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import delete

os.environ.setdefault("DATA_VAULT_MASTER_KEY", os.environ.get("DATA_VAULT_MASTER_KEY", Fernet.generate_key().decode("utf-8")))
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./test_media_upload.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("DISABLE_CLEANUP", "true")
os.environ["DATA_VAULT_MASTER_KEY"] = Fernet.generate_key().decode("utf-8")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AiChatMessage, AiChatSession, User  # noqa: E402
from app.security.data_vault import decrypt_text  # noqa: E402
from app.services import get_current_user, set_llm_client, set_streaming_llm_client  # noqa: E402
from app.services.chatbot_service import (  # noqa: E402
    ChatCompletionResult,
    ChatbotPolicyError,
    LLMClient,
    StreamingLLMClient,
)


class StubLLM(LLMClient):
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, *, messages, temperature: float = 0.2) -> ChatCompletionResult:  # type: ignore[override]
        self.calls += 1
        return ChatCompletionResult(
            content=f"stub-response-{self.calls}",
            prompt_tokens=42,
            completion_tokens=21,
            model="stub-model",
        )


class RejectingLLM(LLMClient):
    def complete(self, *, messages, temperature: float = 0.2) -> ChatCompletionResult:  # type: ignore[override]
        raise ChatbotPolicyError(detail={"message": "Your request violates our content policy.", "violations": ["profanity"]})


class RejectingStreamLLM(StreamingLLMClient):
    async def stream(self, *, messages, temperature: float = 0.2) -> AsyncIterator[str]:  # type: ignore[override]
        raise ChatbotPolicyError(detail={"message": "Your request violates our content policy.", "violations": ["toxicity"]})
        if False:  # pragma: no cover - generator stub
            yield ""


@pytest.fixture(scope="module", autouse=True)
def _create_schema() -> Iterator[None]:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_database() -> Iterator[None]:
    with SessionLocal() as session:
        session.execute(delete(AiChatMessage))
        session.execute(delete(AiChatSession))
        session.execute(delete(User))
        session.commit()
    yield


@pytest.fixture(autouse=True)
def stub_llm() -> Iterator[StubLLM]:
    client = StubLLM()
    set_llm_client(client)
    yield client
    set_llm_client(None)


@pytest.fixture
def user_factory() -> Callable[[str], User]:
    def _factory(username: str) -> User:
        with SessionLocal() as session:
            user = User(username=username, hashed_password="test-hash")
            session.add(user)
            session.commit()
            session.refresh(user)
            return user
    return _factory


@pytest.fixture
def authed_client() -> Iterator[Callable[[User], TestClient]]:
    with TestClient(app) as client:
        def _with_user(user: User) -> TestClient:
            def _override() -> User:
                return user
            app.dependency_overrides[get_current_user] = _override
            return client
        yield _with_user
    app.dependency_overrides.clear()


def test_chatbot_endpoint_persists_encrypted_transcript(authed_client, user_factory):
    user = user_factory("ai-tester")
    client = authed_client(user)

    response = client.post("/chatbot/test", json={"message": "Plan my day"})
    assert response.status_code == 200
    body = response.json()
    assert body["persona"] == "companion"
    assert len(body["messages"]) == 2  # user + assistant exchange

    session_id = UUID(body["session_id"])
    with SessionLocal() as session:
        stored_session = session.get(AiChatSession, session_id)
        assert stored_session is not None
        stored_messages = (
            session.query(AiChatMessage)
            .filter(AiChatMessage.session_id == session_id)
            .order_by(AiChatMessage.created_at.asc())
            .all()
        )
        assert len(stored_messages) == 2
        user_record = stored_messages[0]
        assistant_record = stored_messages[1]
        user_cipher = cast(str, user_record.content_ciphertext)
        assistant_cipher = cast(str, assistant_record.content_ciphertext)
        assert decrypt_text(user_cipher) == "Plan my day"
        assert decrypt_text(assistant_cipher).startswith("stub-response")
        assert user_cipher != "Plan my day"
        assert cast(str | None, assistant_record.model) == "stub-model"


def test_chatbot_session_listing(authed_client, user_factory):
    user = user_factory("ai-scribe")
    client = authed_client(user)
    first = client.post("/chatbot/test", json={"message": "Share trending posts"})
    assert first.status_code == 200

    sessions_response = client.get("/chatbot/sessions")
    assert sessions_response.status_code == 200
    payload = sessions_response.json()
    assert len(payload) == 1
    assert payload[0]["persona"] == "companion"
    assert payload[0]["last_message_preview"].startswith("stub-response")


def test_chatbot_policy_violation_is_returned_to_client(authed_client, user_factory, stub_llm):
    user = user_factory("policy-block")
    client = authed_client(user)

    rejecting_client = RejectingLLM()
    set_llm_client(rejecting_client)

    response = client.post("/chatbot/test", json={"message": "Say hi"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["violations"] == ["profanity"]
    assert "violates" in detail["message"].lower()

    set_llm_client(stub_llm)


def test_streaming_policy_violation_returns_detail(authed_client, user_factory):
    user = user_factory("policy-stream")
    client = authed_client(user)
    rejecting_stream = RejectingStreamLLM()
    set_streaming_llm_client(rejecting_stream)
    try:
        response = client.post(
            "/chatbot/messages/stream",
            json={
                "message": "Tell me a joke",
                "persona": "default",
                "include_public_context": False,
            },
        )
    finally:
        set_streaming_llm_client(None)
    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["violations"] == ["toxicity"]
