"""Post related API routes backed by PostgreSQL and DigitalOcean Spaces."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User
from ..schemas import (
    PostCommentCreate,
    PostCommentListResponse,
    PostCommentResponse,
    PostEngagementResponse,
    PostFeedResponse,
    PostResponse,
)
from ..services import (
    create_post_comment,
    create_post_record,
    delete_post_record,
    get_current_user,
    get_optional_user,
    list_post_comments,
    list_feed_records,
    set_post_dislike_state,
    set_post_like_state,
    update_post_record,
)
from ..services.media_crypto import reveal_media_value
from ..services.realtime import feed_updates_manager

router = APIRouter(prefix="/posts", tags=["posts"])

logger = logging.getLogger(__name__)


def _serialize_post_model(post) -> PostResponse:
    response = PostResponse.model_validate(post)
    response.media_url = reveal_media_value(response.media_url)
    return response


@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post_endpoint(
    caption: str = Form(..., min_length=1),
    media_asset_id: Optional[str] = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """Create a new post optionally storing an uploaded file in Spaces.

    The endpoint expects ``multipart/form-data`` when a file is supplied. If no
    file accompanies the request, the client may still submit a form payload
    containing only ``caption`` and ``user_id``.
    """

    if media_asset_id is not None and media_asset_id.strip() == "":
        media_asset_id = None

    if file is not None and media_asset_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a file upload or a media_asset_id, not both",
        )

    post = await create_post_record(
        db,
        user_id=current_user.id,
        caption=caption,
        media_asset_id=media_asset_id,
        file=file,
    )

    try:
        await feed_updates_manager.broadcast(
            {
                "type": "post_created",
                "post_id": str(post.id),
                "user_id": str(current_user.id),
                "created_at": post.created_at.isoformat() if getattr(post, "created_at", None) else None,
            }
        )
    except Exception:  # pragma: no cover - best effort logging
        logger.exception("Failed to broadcast feed update")

    return _serialize_post_model(post)


@router.patch("/{post_id}", response_model=PostResponse)
async def update_post_endpoint(
    post_id: UUID,
    caption: str | None = Form(None),
    media_asset_id: str | None = Form(None),
    remove_media: bool = Form(False),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    post = await update_post_record(
        db,
        post_id=post_id,
        requester_id=current_user.id,
        requester_role=getattr(current_user, "role", None),
        caption=caption,
        media_asset_id=media_asset_id,
        file=file,
        remove_media=remove_media,
    )
    return _serialize_post_model(post)


@router.get("/feed", response_model=PostFeedResponse)
async def feed_endpoint(
    db: Session = Depends(get_session),
    current_user: User | None = Depends(get_optional_user),
) -> PostFeedResponse:
    viewer_id = current_user.id if current_user else None
    posts = [PostResponse.model_validate(item) for item in list_feed_records(db, viewer_id=viewer_id)]
    return PostFeedResponse(items=posts)


@router.get("/by-user/{username}", response_model=PostFeedResponse)
async def posts_by_user_endpoint(
    username: str,
    db: Session = Depends(get_session),
    current_user: User | None = Depends(get_optional_user),
) -> PostFeedResponse:
    stmt = select(User).where(User.username == username)
    user = db.scalars(stmt).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    viewer_id = current_user.id if current_user else None
    posts = [
        PostResponse.model_validate(item)
        for item in list_feed_records(db, viewer_id=viewer_id, author_id=user.id)
    ]
    return PostFeedResponse(items=posts)


@router.post("/{post_id}/likes", response_model=PostEngagementResponse)
async def like_post_endpoint(
    post_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PostEngagementResponse:
    payload = set_post_like_state(db, post_id=post_id, user_id=current_user.id, should_like=True)
    return PostEngagementResponse(**payload)


@router.delete("/{post_id}/likes", response_model=PostEngagementResponse)
async def unlike_post_endpoint(
    post_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PostEngagementResponse:
    payload = set_post_like_state(db, post_id=post_id, user_id=current_user.id, should_like=False)
    return PostEngagementResponse(**payload)


@router.post("/{post_id}/dislikes", response_model=PostEngagementResponse)
async def dislike_post_endpoint(
    post_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PostEngagementResponse:
    payload = set_post_dislike_state(db, post_id=post_id, user_id=current_user.id, should_dislike=True)
    return PostEngagementResponse(**payload)


@router.delete("/{post_id}/dislikes", response_model=PostEngagementResponse)
async def remove_dislike_endpoint(
    post_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PostEngagementResponse:
    payload = set_post_dislike_state(db, post_id=post_id, user_id=current_user.id, should_dislike=False)
    return PostEngagementResponse(**payload)


@router.get("/{post_id}/comments", response_model=PostCommentListResponse)
async def list_post_comments_endpoint(
    post_id: UUID,
    db: Session = Depends(get_session),
) -> PostCommentListResponse:
    items = list_post_comments(db, post_id=post_id)
    return PostCommentListResponse(items=[PostCommentResponse(**item) for item in items])


@router.post("/{post_id}/comments", response_model=PostCommentResponse, status_code=status.HTTP_201_CREATED)
async def create_post_comment_endpoint(
    post_id: UUID,
    payload: PostCommentCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PostCommentResponse:
    comment = create_post_comment(
        db,
        post_id=post_id,
        author=current_user,
        content=payload.content,
        parent_id=payload.parent_id,
    )
    return PostCommentResponse(**comment)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post_endpoint(
    post_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    delete_post_record(
        db,
        post_id=post_id,
        requester_id=current_user.id,
        requester_role=getattr(current_user, "role", None),
        delete_media=True,
    )
