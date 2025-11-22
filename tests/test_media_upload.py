"""Integration tests for media upload and asset reuse flows."""
from __future__ import annotations

import os
from io import BytesIO
from typing import Iterator, cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

# Ensure the database URL and JWT secret are available before importing application modules.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./test_media_upload.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("DISABLE_CLEANUP", "true")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import MediaAsset, Post, User  # noqa: E402
from app.services import post_service, spaces_service  # noqa: E402
from app.services.spaces_service import SpacesUploadResult  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _create_schema() -> Iterator[None]:
    """Create all tables needed for the test module."""

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_database() -> Iterator[None]:
    """Remove persisted rows and reset cached Spaces configuration between tests."""

    with SessionLocal() as session:
        session.execute(delete(Post))
        session.execute(delete(MediaAsset))
        session.execute(delete(User))
        session.commit()

    spaces_service.load_spaces_config.cache_clear()
    spaces_service.get_spaces_client.cache_clear()
    yield


@pytest.fixture
def test_user() -> User:
    """Persist and return a test user for authenticated requests."""

    with SessionLocal() as session:
        user = User(
            username=f"test-user-{uuid4().hex[:8]}",
            hashed_password="not-a-real-hash",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture
def authed_client(test_user: User) -> Iterator[tuple[TestClient, User]]:
    """Yield a TestClient with authentication overridden for the supplied user."""

    from app.services import get_current_user

    def _override_current_user() -> User:
        return test_user

    app.dependency_overrides[get_current_user] = _override_current_user
    with TestClient(app) as client:
        yield client, test_user
    app.dependency_overrides.clear()


def test_upload_fails_when_spaces_config_missing(authed_client, monkeypatch):
    client, _ = authed_client

    # Remove required environment variables so the configuration loader fails.
    for var in ("DO_SPACES_KEY", "DO_SPACES_SECRET", "DO_SPACES_REGION", "DO_SPACES_NAME", "DO_SPACES_ENDPOINT"):
        monkeypatch.delenv(var, raising=False)
    spaces_service.load_spaces_config.cache_clear()

    response = client.post(
        "/posts/",
        data={"caption": "hi"},
        files={"file": ("demo.png", BytesIO(b"binary"), "image/png")},
    )

    assert response.status_code == 500
    assert "DigitalOcean Spaces" in response.json()["detail"]


def test_upload_creates_media_asset_with_complete_metadata(authed_client, monkeypatch):
    client, user = authed_client

    # Provide placeholder Spaces configuration for validation.
    monkeypatch.setenv("DO_SPACES_KEY", "key")
    monkeypatch.setenv("DO_SPACES_SECRET", "secret")
    monkeypatch.setenv("DO_SPACES_REGION", "nyc3")
    monkeypatch.setenv("DO_SPACES_NAME", "bucket")
    monkeypatch.setenv("DO_SPACES_ENDPOINT", "https://bucket.nyc3.digitaloceanspaces.com")
    spaces_service.load_spaces_config.cache_clear()

    created_assets: list[MediaAsset] = []

    async def _fake_upload(
        file, *, folder: str = "uploads", client=None, db=None, user_id=None
    ) -> SpacesUploadResult:
        assert db is not None
        asset = MediaAsset(
            user_id=user_id,
            key=f"{folder}/fake-{uuid4().hex}.png",
            url="https://example.test/fake.png",
            bucket="bucket",
            content_type=file.content_type or "application/octet-stream",
            folder=folder,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        created_assets.append(asset)
        return SpacesUploadResult(
            asset_id=cast(UUID, asset.id),
            url=cast(str, asset.url),
            key=cast(str, asset.key),
            bucket=cast(str, asset.bucket),
            content_type=cast(str, asset.content_type),
        )

    monkeypatch.setattr(post_service, "upload_file_to_spaces", _fake_upload)

    response = client.post(
        "/posts/",
        data={"caption": "new post"},
        files={"file": ("demo.png", BytesIO(b"binary"), "image/png")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["media_asset_id"] == str(created_assets[0].id)
    assert payload["media_url"] == created_assets[0].url
    assert created_assets[0].user_id == user.id

    with SessionLocal() as session:
        persisted_post = session.get(Post, UUID(payload["id"]))
        assert persisted_post is not None
        persisted_media_asset_id = cast(UUID | None, persisted_post.media_asset_id)
        persisted_media_url = cast(str | None, persisted_post.media_url)
        assert persisted_media_asset_id == created_assets[0].id
        assert persisted_media_url == created_assets[0].url


def test_reuse_existing_media_asset(authed_client):
    client, user = authed_client

    with SessionLocal() as session:
        asset = MediaAsset(
            user_id=user.id,
            key="posts/existing-key",
            url="https://example.test/existing.png",
            bucket="bucket",
            content_type="image/png",
            folder="posts",
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)

    response = client.post(
        "/posts/",
        data={"caption": "reuse", "media_asset_id": str(asset.id)},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["media_asset_id"] == str(asset.id)
    assert payload["media_url"] == asset.url