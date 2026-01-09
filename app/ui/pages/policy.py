"""Privacy policy and community guidelines pages."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..template_helpers import render_template

router = APIRouter()


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_policy(request: Request) -> HTMLResponse:
    return render_template(
        request,
        "privacy.html",
        {
            "page_title": "Privacy Policy",
            "active_nav": None,
            "policy_last_updated": date.today().isoformat(),
        },
    )


@router.get("/community-guidelines", response_class=HTMLResponse)
async def community_guidelines(request: Request) -> HTMLResponse:
    return render_template(
        request,
        "community_guidelines.html",
        {
            "page_title": "Community Guidelines",
            "active_nav": None,
            "policy_last_updated": date.today().isoformat(),
        },
    )


__all__ = ["router"]
