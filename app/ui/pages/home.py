"""Home/feed page surface."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..template_helpers import render_template

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def feed(request: Request) -> HTMLResponse:
    """Render the main feed experience."""

    return render_template(
        request,
        "home.html",
        {
            "page_title": "Feed",
            "active_nav": "/",
        },
    )
