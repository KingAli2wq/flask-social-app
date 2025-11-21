"""DigitalOcean Spaces integration helpers."""
from __future__ import annotations

import logging
import os
import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, cast
from urllib.parse import urlparse

from boto3.session import Session
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as OrmSession

from ..db import MediaAsset

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpacesConfig:
    """Runtime configuration extracted from environment variables."""

    key: str
    secret: str
    region: str
    bucket: str
    endpoint: str


@dataclass(frozen=True)
class SpacesUploadResult:
    """Metadata returned after uploading a file to Spaces."""

    asset_id: uuid.UUID | None
    url: str
    key: str
    bucket: str
    content_type: str


class SpacesUploadError(RuntimeError):
    """Raised when an upload to DigitalOcean Spaces fails."""


@lru_cache(maxsize=1)
def get_spaces_config() -> SpacesConfig:
    """Load and validate DigitalOcean Spaces configuration from the environment."""

    required: dict[str, str | None] = {
        "DO_SPACES_KEY": os.getenv("DO_SPACES_KEY"),
        "DO_SPACES_SECRET": os.getenv("DO_SPACES_SECRET"),
        "DO_SPACES_REGION": os.getenv("DO_SPACES_REGION"),
        "DO_SPACES_NAME": os.getenv("DO_SPACES_NAME"),
        "DO_SPACES_ENDPOINT": os.getenv("DO_SPACES_ENDPOINT"),
    }

    missing = [name for name, value in required.items() if not value or not value.strip()]
    if missing:
        raise RuntimeError(
            "Missing required Spaces configuration: " + ", ".join(sorted(missing))
        )

    key = cast(str, required["DO_SPACES_KEY"]).strip()
    secret = cast(str, required["DO_SPACES_SECRET"]).strip()
    region = cast(str, required["DO_SPACES_REGION"]).strip()
    bucket = cast(str, required["DO_SPACES_NAME"]).strip()
    endpoint_raw = cast(str, required["DO_SPACES_ENDPOINT"]).strip()

    endpoint = endpoint_raw.rstrip("/")
    parsed = urlparse(endpoint)
    if not parsed.scheme:
        logger.warning("DO_SPACES_ENDPOINT is missing a URL scheme; assuming https://")
        endpoint = f"https://{endpoint.lstrip(':/')}"
        parsed = urlparse(endpoint)

    host = parsed.netloc or parsed.path
    if not host:
        message = "DO_SPACES_ENDPOINT must include a hostname."
        logger.warning(message)
        raise RuntimeError(message)

    if not host.endswith(".digitaloceanspaces.com"):
        message = (
            "DO_SPACES_ENDPOINT must point to a DigitalOcean Spaces hostname (*.digitaloceanspaces.com)."
        )
        logger.warning("%s Provided value: %s", message, endpoint)
        raise RuntimeError(message)

    endpoint = parsed.geturl().rstrip("/")

    return SpacesConfig(key=key, secret=secret, region=region, bucket=bucket, endpoint=endpoint)


@lru_cache(maxsize=1)
def get_spaces_client() -> BaseClient:
    """Create a singleton boto3 client for Spaces interactions."""

    config = get_spaces_config()
    session = Session()
    return session.client(
        "s3",
        region_name=config.region,
        endpoint_url=config.endpoint,
        aws_access_key_id=config.key,
        aws_secret_access_key=config.secret,
    )


def _sanitize_segments(parts: Iterable[str]) -> list[str]:
    """Sanitize path segments to be safe for object keys."""

    sanitized: list[str] = []
    for part in parts:
        if part in {"", ".", ".."}:
            continue
        cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", part.strip())
        cleaned = re.sub(r"-+", "-", cleaned).strip("-._")
        if cleaned:
            sanitized.append(cleaned)
    return sanitized


def _object_key(filename: str | None, folder: str) -> str:
    """Generate a namespaced object key anchored within the requested folder."""

    extension = Path(filename or "").suffix.lower()
    if extension and not re.fullmatch(r"\.[A-Za-z0-9]{1,10}", extension):
        extension = ""

    folder_segments = _sanitize_segments((folder or "uploads").replace("\\", "/").split("/"))
    safe_folder = "/".join(folder_segments) or "uploads"

    unique_name = uuid.uuid4().hex
    key = f"{safe_folder}/{unique_name}{extension}" if safe_folder else f"{unique_name}{extension}"
    return key.replace("//", "/").lstrip("/")


def build_public_url(key: str) -> str:
    """Build the public URL for an object stored in DigitalOcean Spaces."""

    config = get_spaces_config()
    normalized_key = key.lstrip("/")
    endpoint = config.endpoint.rstrip("/")
    return f"{endpoint}/{normalized_key}" if normalized_key else endpoint


async def upload_file_to_spaces(
    file: UploadFile,
    *,
    folder: str = "uploads",
    client: BaseClient | None = None,
    db: OrmSession | None = None,
    user_id: uuid.UUID | None = None,
) -> SpacesUploadResult:
    """Upload an ``UploadFile`` to Spaces and return its public metadata."""

    config = get_spaces_config()
    s3_client = client or get_spaces_client()
    key = _object_key(file.filename, folder)
    content_type = (file.content_type or "application/octet-stream").strip() or "application/octet-stream"
    file_obj = getattr(file, "file", None)
    if file_obj is None:
        raise SpacesUploadError("UploadFile is missing an underlying file buffer.")

    def _upload() -> None:
        try:
            file_obj.seek(0)
            s3_client.upload_fileobj(
                file_obj,
                config.bucket,
                key,
                ExtraArgs={"ACL": "public-read", "ContentType": content_type},
            )
        except (ClientError, BotoCoreError) as exc:  # pragma: no cover - network errors hard to reproduce
            logger.exception("Upload to DigitalOcean Spaces failed: %s", exc)
            raise SpacesUploadError("Upload to DigitalOcean Spaces failed") from exc
        except Exception as exc:  # pragma: no cover - defensive programming
            logger.exception("Unexpected error during Spaces upload")
            raise SpacesUploadError("Unexpected error during Spaces upload") from exc

    await run_in_threadpool(_upload)

    url = build_public_url(key)

    asset_id: uuid.UUID | None = None
    if db is not None:
        asset = MediaAsset(
            user_id=user_id,
            key=key,
            url=url,
            bucket=config.bucket,
            content_type=content_type,
            folder=folder,
        )
        try:
            db.add(asset)
            db.commit()
            db.refresh(asset)
            asset_id = asset.id
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Failed to persist media metadata for key %s", key)
            raise SpacesUploadError("Failed to persist media metadata") from exc

    return SpacesUploadResult(asset_id=asset_id, url=url, key=key, bucket=config.bucket, content_type=content_type)


__all__ = [
    "SpacesConfig",
    "SpacesUploadError",
    "SpacesUploadResult",
    "build_public_url",
    "get_spaces_client",
    "get_spaces_config",
    "upload_file_to_spaces",
]
