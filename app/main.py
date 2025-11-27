"""Application entry point for the FastAPI backend."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Iterable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import create_session, init_db
from .routers import (
    auth_router,
    friends_router,
    media_router,
    messages_router,
    notifications_router,
    posts_router,
    profiles_router,
    realtime_router,
    uploads_router,
)
from .services import CleanupError, run_cleanup
from .ui import router as ui_router

logger = logging.getLogger(__name__)

# Resolve runtime configuration (including droplet IPv4) via the shared settings helper.
settings = get_settings()
APP_NAME = settings.app_name
API_VERSION = settings.api_version
DROPLET_HOST = settings.droplet_host
DISABLE_CLEANUP = os.getenv("DISABLE_CLEANUP", "").lower() == "true" or os.getenv("PYTEST_CURRENT_TEST") is not None

app = FastAPI(title=APP_NAME, version=API_VERSION)

cors_origins = os.getenv("CORS_ORIGINS")
if cors_origins:
    origins: Iterable[str] = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
else:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ui_router)
app.include_router(auth_router)
app.include_router(friends_router)
app.include_router(media_router)
app.include_router(posts_router)
app.include_router(messages_router)
app.include_router(notifications_router)
app.include_router(profiles_router)
app.include_router(realtime_router)
app.include_router(uploads_router)

_CLEANUP_INTERVAL = timedelta(hours=24)
_CLEANUP_RETENTION = timedelta(days=2)
_cleanup_task: asyncio.Task[None] | None = None
_cleanup_stop = asyncio.Event()


def _mount_static(directory: Path, route: str, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    app.mount(route, StaticFiles(directory=str(directory), check_dir=False), name=name)


async def _run_cleanup_once() -> None:
    """Execute a single cleanup pass in a worker thread."""

    try:
        summary = await asyncio.to_thread(run_cleanup, create_session, retention=_CLEANUP_RETENTION)
        logger.info(
            "Cleanup summary (posts=%d, direct_messages=%d, group_messages=%d, notifications=%d, total=%d)",
            summary.posts,
            summary.direct_messages,
            summary.group_messages,
            summary.notifications,
            summary.total,
        )
    except CleanupError:
        logger.exception("Scheduled cleanup failed")
    except Exception:  # pragma: no cover - defensive
        logger.exception("Unexpected error during cleanup run")


async def _cleanup_loop() -> None:
    """Background task that runs cleanup on a fixed interval."""

    while not _cleanup_stop.is_set():
        await _run_cleanup_once()
        try:
            await asyncio.wait_for(_cleanup_stop.wait(), timeout=_CLEANUP_INTERVAL.total_seconds())
        except asyncio.TimeoutError:
            continue


@app.on_event("startup")
async def _startup() -> None:
    """Ensure database schema and background tasks are ready before serving."""

    try:
        init_db()
    except Exception:  # pragma: no cover - best effort logging
        logger.exception("Database initialisation failed")
        raise

    # Surface the resolved droplet IPv4 so operators can verify connectivity.
    logger.info("Connected to droplet (IPv4): %s", DROPLET_HOST)

    if DISABLE_CLEANUP:
        logger.info("Background cleanup disabled (testing mode)")
        return

    # Run a cleanup pass immediately on startup.
    await _run_cleanup_once()

    # Schedule periodic cleanup every 24 hours.
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_stop.clear()
        _cleanup_task = asyncio.create_task(_cleanup_loop())


@app.on_event("shutdown")
async def _shutdown() -> None:
    """Stop background tasks cleanly during application shutdown."""

    if DISABLE_CLEANUP:
        return

    _cleanup_stop.set()
    if _cleanup_task is not None:
        try:
            await _cleanup_task
        except asyncio.CancelledError:  # pragma: no cover - defensive
            pass


@app.get("/api", tags=["system"])
def api_info() -> dict[str, str]:
    return {"service": APP_NAME, "version": API_VERSION}


@app.get("/health", tags=["system"])
async def healthcheck() -> dict[str, str]:
    """Report the IPv4 address the backend is configured to use."""

    return {"droplet_ipv4": DROPLET_HOST}



MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "media"))
VIDEOS_ROOT = Path(os.getenv("VIDEOS_ROOT", "videos"))

# Serve the ENTIRE static folder
UI_STATIC_ROOT = Path(__file__).resolve().parent / "ui" / "static"

_mount_static(MEDIA_ROOT, "/media", "media")
_mount_static(VIDEOS_ROOT, "/videos", "videos")
_mount_static(UI_STATIC_ROOT, "/assets", "assets")



