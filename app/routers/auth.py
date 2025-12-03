"""Authentication related API routes backed by PostgreSQL."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User
from ..schemas import AuthResponse, LoginRequest, ProfileResponse, RegisterRequest
from ..services import authenticate_user, create_access_token, get_current_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_profile_response(user: User) -> ProfileResponse:
    return ProfileResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        bio=user.bio,
        location=user.location,
        website=user.website,
        avatar_url=user.avatar_url,
        role=getattr(user, "role", None),
        created_at=user.created_at,
        last_active_at=user.last_active_at,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register_endpoint(
    payload: RegisterRequest,
    db: Session = Depends(get_session),
) -> AuthResponse:
    user, token = register_user(db, payload)
    return AuthResponse(access_token=token, user_id=user.id, bio=user.bio, role=getattr(user, "role", None))


@router.post("/login", response_model=AuthResponse)
async def login_endpoint(
    payload: LoginRequest,
    db: Session = Depends(get_session),
) -> AuthResponse:
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user_id=user.id, bio=user.bio, role=getattr(user, "role", None))


@router.get("/me", response_model=ProfileResponse)
async def me_endpoint(current_user: User = Depends(get_current_user)) -> ProfileResponse:
    return _to_profile_response(current_user)
