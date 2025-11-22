from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse

from ..template_helpers import render_template
from ...services import get_current_user
from ...models import User

router = APIRouter()


@router.get("/profile", response_class=HTMLResponse)
async def profile(
    request: Request,
    current_user: User = Depends(get_current_user)
) -> HTMLResponse:

    profile_data = {
        "avatar_url": current_user.avatar_url,
        "bio": current_user.bio,
        "location": current_user.location,
        "website": current_user.website,
    }

    return render_template(
        request,
        "profile.html",
        {
            "page_title": "Profile",
            "active_nav": "/profile",
            "username": current_user.username,
            "profile": profile_data,
        },
    )
