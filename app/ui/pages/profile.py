"""Profile detail and editing page."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..template_helpers import render_template

router = APIRouter()


@router.get("/profile", response_class=HTMLResponse)
async def profile(request: Request) -> HTMLResponse:
    return render_template(
        request,
        "profile.html",
        {
            "page_title": "Profile",
            "active_nav": "/profile",
        },
    )
