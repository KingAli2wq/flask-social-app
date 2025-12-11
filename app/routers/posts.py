"""Post related API routes backed by PostgreSQL and DigitalOcean Spaces."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import create_session, get_session
from ..models import Post, PostComment, User
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
    get_post_engagement_snapshot,
    get_optional_user,
    respond_to_ai_mention_in_comment,
    respond_to_ai_mention_in_post,
    list_post_comments,
    list_feed_records,
    set_post_dislike_state,
    set_post_like_state,
    update_post_record,
)
from ..services.media_crypto import reveal_media_value
from ..services.realtime import feed_updates_manager
from ..services.moderation_service import ModerationResult, moderate_text

router = APIRouter(prefix="/posts", tags=["posts"])

logger = logging.getLogger(__name__)


def _serialize_post_model(post) -> PostResponse:
    response = PostResponse.model_validate(post)
    response.media_url = reveal_media_value(response.media_url)
    return response


async def _safe_feed_broadcast(message: dict[str, Any]) -> None:
    if not message:
        return
    try:
        await feed_updates_manager.broadcast(message)
    except Exception:  # pragma: no cover - best effort logging
        logger.exception("Failed to broadcast feed update")


async def _broadcast_engagement_snapshot(snapshot: dict[str, Any]) -> None:
    post_id = snapshot.get("post_id")
    if not post_id:
        return
    await _safe_feed_broadcast(
        {
            "type": "post_engagement_updated",
            "post_id": str(post_id),
            "like_count": int(snapshot.get("like_count") or 0),
            "dislike_count": int(snapshot.get("dislike_count") or 0),
            "comment_count": int(snapshot.get("comment_count") or 0),
        }
    )


async def _broadcast_comment_created(comment: dict[str, Any], snapshot: dict[str, Any] | None = None) -> None:
    post_id = comment.get("post_id")
    if not post_id:
        return
    message: dict[str, Any] = {
        "type": "post_comment_created",
        "post_id": str(post_id),
        "comment": comment,
    }
    if snapshot:
        message["counts"] = {
            "like_count": int(snapshot.get("like_count") or 0),
            "dislike_count": int(snapshot.get("dislike_count") or 0),
            "comment_count": int(snapshot.get("comment_count") or 0),
        }
    await _safe_feed_broadcast(message)


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

    moderation: ModerationResult = moderate_text(caption)
    if not moderation.is_allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Your post violates our community guidelines.",
                "reasons": moderation.reasons,
            },
        )

    post = await create_post_record(
        db,
        user_id=current_user.id,
        caption=caption,
        media_asset_id=media_asset_id,
        file=file,
    )

    await _safe_feed_broadcast(
        {
            "type": "post_created",
            "post_id": str(post.id),
            "user_id": str(current_user.id),
            "created_at": post.created_at.isoformat() if getattr(post, "created_at", None) else None,
        }
    )

    _spawn_ai_reply_for_post(post_id=post.id, actor_id=current_user.id)

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
    await _broadcast_engagement_snapshot(payload)
    return PostEngagementResponse(**payload)


@router.delete("/{post_id}/likes", response_model=PostEngagementResponse)
async def unlike_post_endpoint(
    post_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PostEngagementResponse:
    payload = set_post_like_state(db, post_id=post_id, user_id=current_user.id, should_like=False)
    await _broadcast_engagement_snapshot(payload)
    return PostEngagementResponse(**payload)


@router.post("/{post_id}/dislikes", response_model=PostEngagementResponse)
async def dislike_post_endpoint(
    post_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PostEngagementResponse:
    payload = set_post_dislike_state(db, post_id=post_id, user_id=current_user.id, should_dislike=True)
    await _broadcast_engagement_snapshot(payload)
    return PostEngagementResponse(**payload)


@router.delete("/{post_id}/dislikes", response_model=PostEngagementResponse)
async def remove_dislike_endpoint(
    post_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PostEngagementResponse:
    payload = set_post_dislike_state(db, post_id=post_id, user_id=current_user.id, should_dislike=False)
    await _broadcast_engagement_snapshot(payload)
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
    snapshot = get_post_engagement_snapshot(db, post_id=post_id, viewer_id=current_user.id)
    await _broadcast_comment_created(comment, snapshot)
    await _broadcast_engagement_snapshot(snapshot)
    _spawn_ai_reply_for_comment(post_id=post_id, comment_id=comment.get("id"), actor_id=current_user.id)
    return PostCommentResponse(**comment)


def _spawn_ai_reply_for_post(*, post_id: UUID, actor_id: UUID) -> None:
    asyncio.create_task(_ai_reply_for_post_task(post_id=post_id, actor_id=actor_id))


def _spawn_ai_reply_for_comment(*, post_id: UUID, comment_id: UUID | None, actor_id: UUID) -> None:
    if comment_id is None:
        return
    asyncio.create_task(_ai_reply_for_comment_task(post_id=post_id, comment_id=comment_id, actor_id=actor_id))


async def _ai_reply_for_post_task(*, post_id: UUID, actor_id: UUID) -> None:
    session = create_session()
    try:
        post = session.get(Post, post_id)
        actor = session.get(User, actor_id)
        if post is None or actor is None:
            return
        ai_comment = await respond_to_ai_mention_in_post(session, post=post, actor=actor)
        if not ai_comment:
            return
        snapshot = get_post_engagement_snapshot(session, post_id=post_id, viewer_id=actor_id)
        await _broadcast_comment_created(ai_comment, snapshot)
        await _broadcast_engagement_snapshot(snapshot)
    except Exception:
        logger.exception("AI post mention task failed")
    finally:
        session.close()


async def _ai_reply_for_comment_task(*, post_id: UUID, comment_id: UUID, actor_id: UUID) -> None:
    session = create_session()
    try:
        post = session.get(Post, post_id)
        actor = session.get(User, actor_id)
        if post is None or actor is None:
            return
        comment_row = session.get(PostComment, comment_id)
        if comment_row is None:
            return
        comment_payload = {
            "id": comment_row.id,
            "post_id": comment_row.post_id,
            "user_id": comment_row.user_id,
            "content": comment_row.content,
            "parent_id": comment_row.parent_id,
            "created_at": comment_row.created_at,
        }
        ai_comment = await respond_to_ai_mention_in_comment(session, post=post, comment=comment_payload, actor=actor)
        if not ai_comment:
            return
        snapshot = get_post_engagement_snapshot(session, post_id=post_id, viewer_id=actor_id)
        await _broadcast_comment_created(ai_comment, snapshot)
        await _broadcast_engagement_snapshot(snapshot)
    except Exception:
        logger.exception("AI comment mention task failed")
    finally:
        session.close()


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
