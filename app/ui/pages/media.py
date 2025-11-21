"""Media upload surface."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..template_helpers import render_template

router = APIRouter()


@router.get("/media", response_class=HTMLResponse)
async def media(request: Request) -> HTMLResponse:
    return render_template(
        request,
        "media.html",
        {
            "page_title": "Media Uploads",
            "active_nav": "/media",
        },
    )
