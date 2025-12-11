"""Moderation-focused API endpoints."""
from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User
from ..schemas import (
    ModerationDashboardResponse,
    ModerationMediaDetail,
    ModerationMediaList,
    ModerationPostDetail,
    ModerationPostList,
    ModerationPostUpdateRequest,
    ModerationRoleUpdateRequest,
    ModerationUserDetail,
    ModerationUserList,
    ModerationUserSummary,
    ModerationUserUpdateRequest,
    PostCommentResponse,
    PostCommentUpdate,
)
from ..services import (
    delete_media_asset,
    delete_post_comment,
    delete_moderation_user,
    delete_post_record,
    get_moderation_media_asset,
    get_moderation_post,
    get_moderation_user,
    list_moderation_media_assets,
    list_moderation_posts,
    list_moderation_users,
    load_moderation_dashboard,
    require_owner,
    require_roles,
    update_moderation_user,
    update_post_comment,
    update_post_record,
    update_user_role,
)

router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.get("/dashboard", response_model=ModerationDashboardResponse)
async def moderation_dashboard_endpoint(
    db: Session = Depends(get_session),
    current_user: User = Depends(require_roles("owner", "admin")),
) -> ModerationDashboardResponse:
    return load_moderation_dashboard(db)


@router.get("/users", response_model=ModerationUserList)
async def moderation_users_endpoint(
    skip: int = 0,
    limit: int = 25,
    search: str | None = None,
    active_only: bool = False,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_roles("owner", "admin")),
) -> ModerationUserList:
    return list_moderation_users(db, skip=skip, limit=limit, search=search, active_only=active_only)


@router.get("/users/{user_id}", response_model=ModerationUserDetail)
async def moderation_user_detail_endpoint(
    user_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_roles("owner", "admin")),
) -> ModerationUserDetail:
    return get_moderation_user(db, user_id=user_id)


@router.patch("/users/{user_id}", response_model=ModerationUserDetail)
async def moderation_user_update_endpoint(
    user_id: UUID,
    payload: ModerationUserUpdateRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_owner()),
) -> ModerationUserDetail:
    data = payload.model_dump(exclude_unset=True)
    return update_moderation_user(db, user_id=user_id, payload=data)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def moderation_user_delete_endpoint(
    user_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_owner()),
) -> None:
    delete_moderation_user(db, actor=current_user, user_id=user_id)


@router.patch("/users/{user_id}/role", response_model=ModerationUserSummary)
async def moderation_update_role_endpoint(
    user_id: UUID,
    payload: ModerationRoleUpdateRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_owner()),
) -> ModerationUserSummary:
    return update_user_role(db, actor=current_user, target_user_id=user_id, new_role=payload.role)


@router.get("/posts", response_model=ModerationPostList)
async def moderation_posts_endpoint(
    skip: int = 0,
    limit: int = 25,
    user_id: UUID | None = None,
    search: str | None = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_roles("owner", "admin")),
) -> ModerationPostList:
    return list_moderation_posts(db, skip=skip, limit=limit, user_id=user_id, search=search)


@router.get("/posts/{post_id}", response_model=ModerationPostDetail)
async def moderation_post_detail_endpoint(
    post_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_roles("owner", "admin")),
) -> ModerationPostDetail:
    return get_moderation_post(db, post_id=post_id)


@router.patch("/posts/{post_id}", response_model=ModerationPostDetail)
async def moderation_post_update_endpoint(
    post_id: UUID,
    payload: ModerationPostUpdateRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_roles("owner", "admin")),
) -> ModerationPostDetail:
    await update_post_record(
        db,
        post_id=post_id,
        requester_id=cast(UUID, current_user.id),
        requester_role=getattr(current_user, "role", None),
        caption=payload.caption,
        media_asset_id=payload.media_asset_id,
        remove_media=bool(payload.remove_media),
    )
    return get_moderation_post(db, post_id=post_id)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def moderation_delete_post_endpoint(
    post_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_roles("owner", "admin")),
) -> None:
    delete_post_record(
        db,
        post_id=post_id,
        requester_id=cast(UUID, current_user.id),
        requester_role=getattr(current_user, "role", None),
        delete_media=True,
    )


@router.patch("/comments/{comment_id}", response_model=PostCommentResponse)
async def moderation_update_comment_endpoint(
    comment_id: UUID,
    payload: PostCommentUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_roles("owner", "admin")),
) -> PostCommentResponse:
    comment = update_post_comment(
        db,
        comment_id=comment_id,
        requester_id=cast(UUID, current_user.id),
        requester_role=getattr(current_user, "role", None),
        content=payload.content,
    )
    return PostCommentResponse(**comment)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def moderation_delete_comment_endpoint(
    comment_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_roles("owner", "admin")),
) -> None:
    delete_post_comment(
        db,
        comment_id=comment_id,
        requester_id=cast(UUID, current_user.id),
        requester_role=getattr(current_user, "role", None),
    )


@router.get("/media", response_model=ModerationMediaList)
async def moderation_media_list_endpoint(
    skip: int = 0,
    limit: int = 25,
    user_id: UUID | None = None,
    search: str | None = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_roles("owner", "admin")),
) -> ModerationMediaList:
    return list_moderation_media_assets(db, skip=skip, limit=limit, user_id=user_id, search=search)


@router.get("/media/{asset_id}", response_model=ModerationMediaDetail)
async def moderation_media_detail_endpoint(
    asset_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_roles("owner", "admin")),
) -> ModerationMediaDetail:
    return get_moderation_media_asset(db, asset_id=asset_id)


@router.delete("/media/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def moderation_media_delete_endpoint(
    asset_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_roles("owner", "admin")),
) -> None:
    delete_media_asset(db, asset_id=asset_id, delete_remote=True)


__all__ = ["router"]
