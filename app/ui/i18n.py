"""Expose UI translation bundles to the client."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.i18n_service import DEFAULT_LOCALE, get_messages, resolve_request_locale

router = APIRouter(prefix="/i18n", include_in_schema=False)


@router.get("/messages")
async def fetch_messages(request: Request):
    locale = resolve_request_locale(request)
    payload = {
        "locale": locale,
        "messages": get_messages(locale),
        "fallback": get_messages(DEFAULT_LOCALE),
    }
    response = JSONResponse(payload)
    response.set_cookie("ui_locale", locale, max_age=60 * 60 * 24 * 365, httponly=False, samesite="lax", path="/")
    response.headers["Content-Language"] = locale
    return response


__all__ = ["router"]
