"""
Auth endpoints.

  POST /auth/register   — email + password
  POST /auth/login      — email + password → access token
  POST /auth/google     — Google ID token credential → access token
  GET  /auth/me         — current user (requires Authorization: Bearer ...)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_session
from app.repositories import users as users_repo
from app.schemas.auth import (
    GoogleAuthRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from app.services import google_auth

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)


def _to_public(user: dict) -> UserPublic:
    return UserPublic(
        user_id=user["user_id"],
        email=user["email"],
        full_name=user["full_name"],
        provider=user["provider"],
        picture=user.get("picture"),
        created_at=user["created_at"],
    )


def _issue(user: dict) -> TokenResponse:
    token = create_access_token(user_id=user["user_id"], email=user["email"])
    return TokenResponse(access_token=token, user=_to_public(user))


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, session: AsyncSession = Depends(get_session)):
    email = req.email.lower()
    existing = await users_repo.get_by_email(session, email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    user = await users_repo.create_local(
        session,
        email=email,
        password_hash=hash_password(req.password),
        full_name=req.full_name.strip() or email,
    )
    await users_repo.touch_last_login(session, user["user_id"])
    return _issue(user)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, session: AsyncSession = Depends(get_session)):
    user = await users_repo.get_by_email(session, req.email.lower())
    if not user or user["provider"] != "local" or not user["password_hash"]:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    await users_repo.touch_last_login(session, user["user_id"])
    return _issue(user)


@router.post("/google", response_model=TokenResponse)
async def google_signin(req: GoogleAuthRequest, session: AsyncSession = Depends(get_session)):
    try:
        identity = await google_auth.verify_credential(req.credential)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {e}")

    # Prefer matching by Google sub (stable). Fall back to email so existing
    # local accounts can link a Google identity transparently.
    user = await users_repo.get_by_google_sub(session, identity["sub"])
    if user is None:
        existing = await users_repo.get_by_email(session, identity["email"])
        if existing:
            raise HTTPException(
                status_code=409,
                detail=(
                    "An account with this email already exists. "
                    "Sign in with your password instead."
                ),
            )
        user = await users_repo.create_google(
            session,
            email=identity["email"],
            full_name=identity["name"],
            google_sub=identity["sub"],
            picture=identity.get("picture"),
        )
    else:
        await users_repo.update_picture_if_changed(
            session, user["user_id"], identity.get("picture")
        )
        user["picture"] = identity.get("picture") or user.get("picture")

    await users_repo.touch_last_login(session, user["user_id"])
    return _issue(user)


@router.get("/me", response_model=UserPublic)
async def me(current = Depends(get_current_user)):
    return _to_public(current)
