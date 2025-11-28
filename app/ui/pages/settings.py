"""Settings page definition."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..template_helpers import render_template

router = APIRouter(prefix="", tags=["settings"], include_in_schema=False)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    return render_template(
        request,
        "settings.html",
        {
            "active_nav": "/settings",
            "page_title": "Settings",
        },
    )


__all__ = ["router"]
