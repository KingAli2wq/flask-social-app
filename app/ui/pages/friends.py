"""Friend search landing page."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..template_helpers import render_template

router = APIRouter()


@router.get("/friends/search", response_class=HTMLResponse)
async def friends_search(request: Request) -> HTMLResponse:
    return render_template(
        request,
        "friends_search.html",
        {
            "page_title": "Find friends",
            "active_nav": "/friends/search",
        },
    )


__all__ = ["router"]
