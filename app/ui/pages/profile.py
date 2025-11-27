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


@router.get("/people/{username}", response_class=HTMLResponse)
async def public_profile(request: Request, username: str) -> HTMLResponse:
    return render_template(
        request,
        "public_profile.html",
        {
            "page_title": f"@{username}",
            "active_nav": "/friends/search",
            "profile_username": username,
        },
    )
