"""Middleware for enforcing Terms and Conditions acceptance."""
from __future__ import annotations

from collections.abc import Iterable, Sequence

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from ..constants import CURRENT_TERMS_VERSION, TERMS_BLOCK_DETAIL
from ..database import SessionLocal
from ..models import User
from ..services.auth_service import decode_access_token


class TermsAcceptanceMiddleware(BaseHTTPMiddleware):
    """Block authenticated requests when the latest terms have not been accepted."""

    def __init__(self, app: ASGIApp, *, exempt_paths: Sequence[str] | None = None) -> None:
        super().__init__(app)
        self._exempt_paths = tuple(exempt_paths or ())

    def _should_skip(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self._exempt_paths)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if self._should_skip(path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return await call_next(request)

        token = auth_header.split(None, 1)[1].strip() if " " in auth_header.strip() else auth_header[7:]

        try:
            user_id = decode_access_token(token)
        except HTTPException:
            # Let the downstream dependency raise the usual 401/403 response.
            return await call_next(request)

        block_response: JSONResponse | None = None
        session = SessionLocal()
        try:
            user = session.get(User, user_id)
            if not user:
                return await call_next(request)

            accepted_version = getattr(user, "accepted_terms_version", None)
            if accepted_version == CURRENT_TERMS_VERSION:
                return await call_next(request)

            block_response = JSONResponse(
                status_code=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
                content={
                    "detail": TERMS_BLOCK_DETAIL,
                    "current_terms_version": CURRENT_TERMS_VERSION,
                },
            )
        finally:
            session.close()

        return block_response


    __all__: Iterable[str] = ["TermsAcceptanceMiddleware"]
