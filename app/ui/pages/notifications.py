"""Notifications list page."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..template_helpers import render_template

router = APIRouter()


@router.get("/notifications", response_class=HTMLResponse)
async def notifications(request: Request) -> HTMLResponse:
    return render_template(
        request,
        "notifications.html",
        {
            "page_title": "Notifications",
            "active_nav": "/notifications",
        },
    )
