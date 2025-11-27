"""Friend management API routes."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import FriendRequest, Friendship, User
from ..schemas.friends import (
    FriendRequestPayload,
    FriendRequestResponse,
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
    friend = friendship.user_b if friendship.user_a_id == viewer.id else friendship.user_a
    return FriendSummary(
        id=friend.id,
        username=friend.username,
        avatar_url=friend.avatar_url,
        chat_id=friendship.thread_id,
        lock_code=friendship.lock_code,
    )


def _request_response(request: FriendRequest) -> FriendRequestResponse:
    return FriendRequestResponse.model_validate(request)


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
