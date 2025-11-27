"""Friend management API routes."""
from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import FriendRequest, Friendship, User
from ..schemas.friends import (
    FriendRequestPayload,
    FriendRequestResponse,
    FriendSearchResponse,
    FriendSearchResult,
    FriendsOverviewResponse,
    FriendSummary,
)
from ..services import (
    get_current_user,
    list_friend_requests,
    list_friends,
    respond_to_request,
    send_friend_request,
)

router = APIRouter(prefix="/friends", tags=["friends"])


def _friend_summary(friendship: Friendship, viewer: User) -> FriendSummary:
    viewer_id = cast(UUID, viewer.id)
    user_a_id = cast(UUID, friendship.user_a_id)
    friend = friendship.user_b if user_a_id == viewer_id else friendship.user_a
    return FriendSummary(
        id=cast(UUID, friend.id),
        username=friend.username,
        avatar_url=friend.avatar_url,
        chat_id=str(friendship.thread_id),
        lock_code=str(friendship.lock_code),
    )


def _request_response(request: FriendRequest) -> FriendRequestResponse:
    return FriendRequestResponse.model_validate(request)


def _status_maps(
    *,
    viewer: User,
    friendships: list[Friendship],
    incoming: list[FriendRequest],
    outgoing: list[FriendRequest],
) -> tuple[set[UUID], set[UUID], set[UUID]]:
    viewer_id = cast(UUID, viewer.id)
    friend_ids: set[UUID] = set()
    for friendship in friendships:
        user_a_id = cast(UUID, friendship.user_a_id)
        friend = friendship.user_b if user_a_id == viewer_id else friendship.user_a
        friend_ids.add(cast(UUID, friend.id))
    incoming_ids = {cast(UUID, req.sender_id) for req in incoming}
    outgoing_ids = {cast(UUID, req.recipient_id) for req in outgoing}
    return friend_ids, incoming_ids, outgoing_ids


@router.get("/", response_model=FriendsOverviewResponse)
async def friends_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FriendsOverviewResponse:
    friendships = list_friends(db, user=current_user)
    incoming, outgoing = list_friend_requests(db, user=current_user)
    return FriendsOverviewResponse(
        friends=[_friend_summary(friendship, current_user) for friendship in friendships],
        incoming_requests=[_request_response(item) for item in incoming],
        outgoing_requests=[_request_response(item) for item in outgoing],
    )


@router.get("/search", response_model=FriendSearchResponse)
async def search_users(
    q: str = Query(..., min_length=2, max_length=150, alias="query"),
    limit: int = Query(12, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FriendSearchResponse:
    query = q.strip()
    if not query:
        return FriendSearchResponse(query="", results=[])

    friendships = list_friends(db, user=current_user)
    incoming, outgoing = list_friend_requests(db, user=current_user)
    friend_ids, incoming_ids, outgoing_ids = _status_maps(
        viewer=current_user,
        friendships=friendships,
        incoming=incoming,
        outgoing=outgoing,
    )

    pattern = f"%{query}%"
    stmt = (
        select(User)
        .where(User.username.ilike(pattern))
        .order_by(User.username.asc())
        .limit(limit)
    )
    candidates = db.scalars(stmt).all()

    results: list[FriendSearchResult] = []
    viewer_id = cast(UUID, current_user.id)
    for candidate in candidates:
        candidate_id = cast(UUID, candidate.id)
        if candidate_id == viewer_id:
            status_label = "self"
        elif candidate_id in friend_ids:
            status_label = "friend"
        elif candidate_id in incoming_ids:
            status_label = "incoming"
        elif candidate_id in outgoing_ids:
            status_label = "outgoing"
        else:
            status_label = "available"
        results.append(
            FriendSearchResult(
                id=candidate_id,
                username=candidate.username,
                avatar_url=candidate.avatar_url,
                bio=candidate.bio,
                status=status_label,
            )
        )

    return FriendSearchResponse(query=query, results=results)


@router.post("/requests", response_model=FriendRequestResponse, status_code=status.HTTP_201_CREATED)
async def send_friend_request_endpoint(
    payload: FriendRequestPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FriendRequestResponse:
    request = send_friend_request(db, sender=current_user, recipient_username=payload.username)
    return _request_response(request)


@router.post("/requests/{request_id}/accept", response_model=FriendRequestResponse)
async def accept_friend_request(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FriendRequestResponse:
    friendship = respond_to_request(db, request_id=request_id, recipient=current_user, accept=True)
    request = db.get(FriendRequest, request_id)
    return _request_response(request)


@router.post("/requests/{request_id}/decline", response_model=FriendRequestResponse)
async def decline_friend_request(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FriendRequestResponse:
    respond_to_request(db, request_id=request_id, recipient=current_user, accept=False)
    request = db.get(FriendRequest, request_id)
    return _request_response(request)


__all__ = ["router"]
