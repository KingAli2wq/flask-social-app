"""Utilities for rendering UI templates with shared context."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

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
    """Return a TemplateResponse with shared UI context."""

    base_context: dict[str, Any] = {
        "request": request,
        "app_name": "SocialSphere",
        "components": _BASE_COMPONENTS,
        "active_nav": None,
        "page_title": "",
    }
    if context:
        base_context.update(context)
    return templates.TemplateResponse(template_name, base_context)
