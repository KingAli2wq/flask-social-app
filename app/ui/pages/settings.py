"""Settings page definition."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from .. import components
from ..template_helpers import render_template
from ...services import get_current_user

router = APIRouter(prefix="", tags=["settings"], include_in_schema=False)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(current_user=Depends(get_current_user)) -> HTMLResponse:
    content = render_template(
        "settings.html",
        {
            "active_nav": "/settings",
            "components": components,
            "current_user": current_user,
        },
    )
    return HTMLResponse(content)


__all__ = ["router"]
