"""Authentication related pages."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..template_helpers import render_template

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login(request: Request) -> HTMLResponse:
    return render_template(
        request,
        "login.html",
        {
            "page_title": "Login",
            "active_nav": None,
        },
    )


@router.get("/register", response_class=HTMLResponse)
async def register(request: Request) -> HTMLResponse:
    return render_template(
        request,
        "register.html",
        {
            "page_title": "Join",
            "active_nav": None,
        },
    )
