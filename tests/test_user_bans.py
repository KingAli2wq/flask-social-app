"""Integration tests covering user ban enforcement."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./test_user_bans.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("DISABLE_CLEANUP", "true")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.constants import CURRENT_TERMS_VERSION  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _create_schema() -> Iterator[None]:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_database() -> Iterator[None]:
    with SessionLocal() as session:
        session.execute(delete(User))
        session.commit()
    yield


def _register(client: TestClient, username: str, password: str) -> dict:
    response = client.post(
        "/auth/register",
        json={"username": username, "password": password, "email": None, "bio": None},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, username: str, password: str):
    return client.post("/auth/login", json={"username": username, "password": password})


def test_banned_user_cannot_login_or_access_me() -> None:
    with TestClient(app) as client:
        reg = _register(client, "banned-user", "password123")
        user_id = UUID(reg["user_id"])

        with SessionLocal() as session:
            user = session.get(User, user_id)
            assert user is not None
            user.banned_at = datetime.now(timezone.utc)
            user.banned_until = datetime.now(timezone.utc) + timedelta(days=7)
            user.ban_reason = "testing"
            session.add(user)
            session.commit()

        login = _login(client, "banned-user", "password123")
        assert login.status_code == 403

        me = client.get("/auth/me", headers={"Authorization": f"Bearer {reg['access_token']}"})
        assert me.status_code == 403


def test_ban_and_unban_endpoints_toggle_access() -> None:
    with TestClient(app) as client:
        owner_reg = _register(client, "owner-user", "password123")
        target_reg = _register(client, "target-user", "password123")

        with SessionLocal() as session:
            owner = session.get(User, UUID(owner_reg["user_id"]))
            assert owner is not None
            owner.role = "owner"
            owner.accepted_terms_version = CURRENT_TERMS_VERSION
            owner.terms_accepted_at = datetime.now(timezone.utc)
            session.add(owner)
            session.commit()

        ban = client.post(
            f"/moderation/users/{target_reg['user_id']}/ban",
            headers={"Authorization": f"Bearer {owner_reg['access_token']}"},
            json={"unit": "days", "value": 2, "reason": "temp"},
        )
        assert ban.status_code == 200, ban.text
        payload = ban.json()
        assert payload["is_banned"] is True

        me = client.get("/auth/me", headers={"Authorization": f"Bearer {target_reg['access_token']}"})
        assert me.status_code == 403

        unban = client.post(
            f"/moderation/users/{target_reg['user_id']}/unban",
            headers={"Authorization": f"Bearer {owner_reg['access_token']}"},
        )
        assert unban.status_code == 200, unban.text
        assert unban.json()["is_banned"] is False

        me_after = client.get("/auth/me", headers={"Authorization": f"Bearer {target_reg['access_token']}"})
        assert me_after.status_code == 200
