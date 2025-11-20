"""Application entry point for the FastAPI backend."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import (
    auth_router,
    media_router,
    messages_router,
    notifications_router,
    posts_router,
    profiles_router,
)

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "Social Backend")
API_VERSION = os.getenv("API_VERSION", "0.1.0")

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

app.include_router(auth_router)
app.include_router(posts_router)
app.include_router(messages_router)
app.include_router(notifications_router)
app.include_router(profiles_router)
app.include_router(media_router)


@app.get("/health", tags=["system"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


def _mount_static(directory: Path, route: str, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    app.mount(route, StaticFiles(directory=str(directory), check_dir=False), name=name)


MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "media"))
VIDEOS_ROOT = Path(os.getenv("VIDEOS_ROOT", "videos"))

_mount_static(MEDIA_ROOT, "/media", "media")
_mount_static(VIDEOS_ROOT, "/videos", "videos")
