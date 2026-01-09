"""Middleware for enforcing the optional app-wide lock cookie."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
import hmac
import os

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from ..services.app_lock_service import (
    is_app_lock_enabled,
    is_unlocked_from_cookie,
    lock_cookie_name,
)


class AppLockMiddleware(BaseHTTPMiddleware):
    """Block API access until the app lock cookie is present.

    Notes:
    - UI pages still render so the overlay can prompt for the password.
    - API routes (and other non-HTML endpoints) are blocked while locked.
    """

    def __init__(self, app: ASGIApp, *, exempt_paths: Sequence[str] | None = None) -> None:
        super().__init__(app)
        self._exempt_paths = tuple(exempt_paths or ())

    def _should_skip(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self._exempt_paths)

    def _is_api_path(self, path: str) -> bool:
        return path.startswith(
            (
                "/ai",
                "/auth",
                "/chatbot",
                "/friends",
                "/follows",
                "/messages",
                "/moderation",
                "/notifications",
                "/posts",
                "/profiles",
                "/realtime",
                "/settings",
                "/spellcheck",
                "/stories",
                "/system",
                "/uploads",
                "/media",
                "/videos",
                "/webhooks/",
            )
        )

    def _should_allow_internal_ai_call(self, request: Request) -> bool:
        """Allow internal server-to-server calls to /ai/* without requiring the app lock cookie.

        This is needed because chatbot features call the /ai/chat proxy via HTTP from within
        the same process, which does not carry browser cookies.
        """

        path = request.url.path
        if not path.startswith("/ai"):
            return False

        client_host = getattr(request.client, "host", None)
        if client_host in {"127.0.0.1", "::1"}:
            return True

        token = os.getenv("SOCIAL_AI_INTERNAL_TOKEN") or ""
        if not token:
            return False

        header_value = request.headers.get("x-social-ai-internal") or ""
        if not header_value:
            return False

        try:
            return hmac.compare_digest(header_value, token)
        except Exception:
            return False

    async def dispatch(self, request: Request, call_next) -> Response:
        if not is_app_lock_enabled():
            return await call_next(request)

        path = request.url.path
        if self._should_skip(path):
            return await call_next(request)

        # Only gate API-style paths; UI can still render to show the lock overlay.
        if not self._is_api_path(path):
            return await call_next(request)

        # Allow internal /ai/* calls (chatbot services proxy through /ai/chat).
        if self._should_allow_internal_ai_call(request):
            return await call_next(request)

        # Allow the unlock endpoints themselves.
        if path.startswith("/system/app-lock/"):
            return await call_next(request)

        token = request.cookies.get(lock_cookie_name())
        if is_unlocked_from_cookie(token):
            return await call_next(request)

        return JSONResponse(
            status_code=status.HTTP_423_LOCKED,
            content={
                "detail": "App is locked. Provide the access password to continue.",
                "locked": True,
            },
        )


__all__: Iterable[str] = ["AppLockMiddleware"]
