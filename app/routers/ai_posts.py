"""AI-assisted post generation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User
from ..schemas import AIGeneratePostRequest, PostResponse
from ..services import create_ai_post, require_roles
from ..services.media_crypto import reveal_media_value

router = APIRouter(prefix="/ai", tags=["ai"])
admin_guard = require_roles("owner", "admin")


def _serialize_post(post) -> PostResponse:
    response = PostResponse.model_validate(post)
    response.media_url = reveal_media_value(response.media_url)
    return response


@router.post("/generate-post", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def generate_ai_post_endpoint(
    payload: AIGeneratePostRequest | None = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(admin_guard),
) -> PostResponse:
    options = payload or AIGeneratePostRequest()
    post = await create_ai_post(
        db,
        max_context_posts=options.max_context_posts,
        lookback_hours=options.lookback_hours,
        temperature=options.temperature,
    )
    return _serialize_post(post)


__all__ = ["router", "admin_guard"]
