"""Authentication related API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..database import FakeDatabase, get_database
from ..models import UserRecord
from ..schemas import AuthResponse, LoginRequest, RegisterRequest, UserPublicProfile
from ..services import authenticate_user, get_current_user, issue_token, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_public_profile(user: UserRecord) -> UserPublicProfile:
    return UserPublicProfile(
        username=user.username,
        email=user.email,
        bio=user.bio,
        location=user.location,
        website=user.website,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register_endpoint(
    payload: RegisterRequest,
    db: FakeDatabase = Depends(get_database),
) -> AuthResponse:
    user = register_user(db, payload)
    token = issue_token(user)
    return AuthResponse(access_token=token)


@router.post("/login", response_model=AuthResponse)
async def login_endpoint(
    payload: LoginRequest,
    db: FakeDatabase = Depends(get_database),
) -> AuthResponse:
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = issue_token(user)
    return AuthResponse(access_token=token)


@router.get("/me", response_model=UserPublicProfile)
async def me_endpoint(current_user: UserRecord = Depends(get_current_user)) -> UserPublicProfile:
    return _to_public_profile(current_user)
