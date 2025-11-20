"""Post related API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from ..database import FakeDatabase, get_database
from ..models import PostRecord, UserRecord
from ..schemas import PostCreate, PostFeedResponse, PostResponse
from ..services import create_post, delete_post, get_current_user, list_feed

router = APIRouter(prefix="/posts", tags=["posts"])


def _to_post_response(post: PostRecord) -> PostResponse:
    return PostResponse(
        id=post.id,
        author=post.author,
        content=post.content,
        attachments=post.attachments,
        created_at=post.created_at,
        updated_at=post.updated_at,
        likes=len(post.likes),
        dislikes=len(post.dislikes),
    )


@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post_endpoint(
    payload: PostCreate,
    current_user: UserRecord = Depends(get_current_user),
    db: FakeDatabase = Depends(get_database),
) -> PostResponse:
    record = create_post(db, current_user, payload)
    return _to_post_response(record)


@router.get("/feed", response_model=PostFeedResponse)
async def feed_endpoint(db: FakeDatabase = Depends(get_database)) -> PostFeedResponse:
    posts = [_to_post_response(item) for item in list_feed(db)]
    return PostFeedResponse(items=posts)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post_endpoint(
    post_id: str,
    current_user: UserRecord = Depends(get_current_user),
    db: FakeDatabase = Depends(get_database),
) -> None:
    delete_post(db, post_id, current_user)
