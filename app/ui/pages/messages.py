"""Messaging and DM surface."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..template_helpers import render_template

router = APIRouter()


@router.get("/messages", response_class=HTMLResponse)
async def messages(request: Request) -> HTMLResponse:
    return render_template(
        request,
        "messages.html",
        {
            "page_title": "Messages",
            "active_nav": "/messages",
        },
    )
