"""Moderation dashboard page."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ...models import User
from ...services import get_optional_user
from ..template_helpers import render_template

router = APIRouter(prefix="", tags=["moderation"], include_in_schema=False)


@router.get("/moderation", response_class=HTMLResponse)
async def moderation_page(
    request: Request,
    current_user: User | None = Depends(get_optional_user),
) -> HTMLResponse:
    viewer_role = getattr(current_user, "role", None) or "user"
    return render_template(
        request,
        "moderation.html",
        {
            "active_nav": "/moderation",
            "page_title": "Moderation",
            "viewer_role": viewer_role,
        },
    )


__all__ = ["router"]
