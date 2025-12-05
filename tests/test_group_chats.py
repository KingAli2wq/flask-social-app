"""Integration tests covering secure group chat flows."""
from __future__ import annotations

import os
from typing import Callable, Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./test_media_upload.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("DISABLE_CLEANUP", "true")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import GroupChat, Message, User  # noqa: E402
from app.services import get_current_user  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _create_schema() -> Iterator[None]:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_database() -> Iterator[None]:
    with SessionLocal() as session:
        session.execute(delete(Message))
        session.execute(delete(GroupChat))
        session.execute(delete(User))
        session.commit()
    yield


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


def test_group_chat_creation_and_encrypted_messages(authed_client, user_factory):
    owner = user_factory("orbit-owner")
    teammate = user_factory("orbit-teammate")
    client = authed_client(owner)

    create_response = client.post(
        "/messages/groups",
        json={"name": "Orbit Control", "members": [teammate.username]},
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["lock_code"]
    group_id = payload["id"]

    message_response = client.post(
        "/messages/send",
        json={"chat_id": group_id, "content": "launch codes"},
    )
    assert message_response.status_code == 201
    body = message_response.json()
    assert body["chat_id"] == group_id
    assert body["content"] == "launch codes"

    with SessionLocal() as session:
        stored = session.get(Message, UUID(body["id"]))
        assert stored is not None
        assert stored.content != "launch codes"  # ciphertext stored at rest
        assert stored.group_chat_id == UUID(group_id)

    thread_response = client.get(f"/messages/{group_id}")
    assert thread_response.status_code == 200
    thread_payload = thread_response.json()
    assert thread_payload["chat_id"] == group_id
    assert thread_payload["messages"][0]["content"] == "launch codes"

    attachments_only = client.post(
        "/messages/send",
        json={"chat_id": group_id, "content": "", "attachments": ["https://example.test/sample.png"]},
    )
    assert attachments_only.status_code == 201
    assert attachments_only.json()["attachments"] == ["https://example.test/sample.png"]


def test_group_invite_flow(authed_client, user_factory):
    owner = user_factory("lumen-owner")
    designer = user_factory("lumen-designer")
    editor = user_factory("lumen-editor")
    client = authed_client(owner)

    create_response = client.post(
        "/messages/groups",
        json={"name": "Lumen Lab", "members": [designer.username]},
    )
    assert create_response.status_code == 201
    group_id = create_response.json()["id"]

    invite_response = client.post(
        f"/messages/groups/{group_id}/members",
        json={"members": [editor.username]},
    )
    assert invite_response.status_code == 200
    members = invite_response.json()["members"]
    assert owner.username in members
    assert designer.username in members
    assert editor.username in members

    groups_response = client.get("/messages/groups")
    assert groups_response.status_code == 200
    assert len(groups_response.json()) == 1

    member_client = authed_client(editor)
    detail_response = member_client.get(f"/messages/groups/{group_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["name"] == "Lumen Lab"
