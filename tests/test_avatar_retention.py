"""Regression tests ensuring avatar assets are not pruned by age-based cleanup."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest
from sqlalchemy import delete

# Ensure the database URL is available before importing application modules.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./test_avatar_retention.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("DISABLE_CLEANUP", "true")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import MediaAsset  # noqa: E402
from app.services.media_service import delete_old_media  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _create_schema() -> Iterator[None]:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_database() -> Iterator[None]:
    with SessionLocal() as session:
        session.execute(delete(MediaAsset))
        session.commit()
    yield


def test_delete_old_media_never_removes_avatars() -> None:
    with SessionLocal() as session:
        old_timestamp = datetime.now(timezone.utc) - timedelta(days=10)

        avatar_asset = MediaAsset(
            user_id=None,
            key="avatars/test-avatar.png",
            url="https://example.test/avatars/test-avatar.png",
            bucket="bucket",
            content_type="image/png",
            folder="avatars",
            created_at=old_timestamp,
        )
        other_asset = MediaAsset(
            user_id=None,
            key="media/test-media.png",
            url="https://example.test/media/test-media.png",
            bucket="bucket",
            content_type="image/png",
            folder="media",
            created_at=old_timestamp,
        )

        session.add_all([avatar_asset, other_asset])
        session.commit()

        removed = delete_old_media(session, older_than=timedelta(days=2))
        assert removed == 1

        remaining_folders = {asset.folder for asset in session.query(MediaAsset).all()}
        assert "avatars" in remaining_folders
        assert "media" not in remaining_folders
