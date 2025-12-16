"""Utilities for rendering UI templates with shared context."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.constants import CURRENT_TERMS_VERSION, TERMS_BLOCK_DETAIL
from app.services.i18n_service import DEFAULT_LOCALE, get_messages, resolve_request_locale, translate
from . import components

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

_BASE_COMPONENTS = {
    "buttons": components.buttons,
    "cards": components.cards,
    "feedback": components.feedback,
    "forms": components.forms,
    "layout": components.layout,
}


def render_template(request: Request, template_name: str, context: dict[str, Any] | None = None):
    """Return a TemplateResponse with shared UI + i18n context."""

    locale = resolve_request_locale(request)
    messages = get_messages(locale)
    default_messages = get_messages(DEFAULT_LOCALE)

    def _t(key: str, default: str | None = None) -> str:
        return translate(locale, key, default)

    base_context: dict[str, Any] = {
        "request": request,
        "app_name": "SocialSphere",
        "components": _BASE_COMPONENTS,
        "active_nav": None,
        "page_title": "",
        "terms_version": CURRENT_TERMS_VERSION,
        "terms_block_message": TERMS_BLOCK_DETAIL,
        "locale": locale,
        "i18n_messages": messages,
        "i18n_default_messages": default_messages,
        "t": _t,
    }
    if context:
        base_context.update(context)

    response = templates.TemplateResponse(template_name, base_context)
    response.set_cookie("ui_locale", locale, max_age=60 * 60 * 24 * 365, httponly=False, samesite="lax", path="/")
    response.headers["Content-Language"] = locale
    return response
