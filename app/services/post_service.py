"""Business logic for working with posts."""
from __future__ import annotations

from typing import List

from fastapi import HTTPException, status

from ..database import FakeDatabase
from ..models import PostRecord, UserRecord
from ..schemas import PostCreate


def create_post(db: FakeDatabase, author: UserRecord, payload: PostCreate) -> PostRecord:
    record = PostRecord(author=author.username, content=payload.content, attachments=payload.attachments)
    db.create_post(record)
    return record


def list_feed(db: FakeDatabase) -> List[PostRecord]:
    return sorted(db.list_posts(), key=lambda post: post.created_at, reverse=True)


def delete_post(db: FakeDatabase, post_id: str, requester: UserRecord) -> None:
    record = db.get_post(post_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if record.author != requester.username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete this post")
    db.delete_post(post_id)


__all__ = ["create_post", "list_feed", "delete_post"]
