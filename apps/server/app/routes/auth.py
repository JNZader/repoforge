"""Authentication routes: GitHub OAuth login/callback, JWT validate, logout."""

import logging
import time
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.config import settings
from app.middleware.auth import CurrentUser
from app.models import User, async_session_factory
from app.models.schemas import AuthValidateResponse, UserInfo

from app.services.github_oauth import (
    exchange_code_for_token,
    generate_state,
    get_github_user,
    validate_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"


def _build_jwt(user: User) -> str:
    """Build a signed JWT for the given user."""
    now = int(time.time())
    payload = {
        "sub": str(user.id),           # UUID — used as user_id in DB queries
        "github_user_id": user.github_id,
        "login": user.github_login,
        "avatar_url": user.avatar_url or "",
        "iat": now,
        "exp": now + settings.JWT_EXPIRATION_SECONDS,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@router.get("/login")
async def login() -> RedirectResponse:
    """Redirect user to GitHub OAuth authorize page."""
    state = generate_state()
    params = urlencode({
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": (
            f"{settings.BACKEND_URL.rstrip('/')}/auth/callback"
            if settings.BACKEND_URL
            else f"{settings.FRONTEND_URL.rstrip('/')}/api/auth/callback"
        ),
        "scope": "read:user",
        "state": state,
    })
    redirect_url = f"{_GITHUB_AUTHORIZE_URL}?{params}"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.get("/callback")
async def callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    """Process GitHub OAuth callback: validate state, exchange code, upsert user, return JWT."""
    frontend_base = settings.FRONTEND_URL.rstrip("/")

    # GitHub denied access
    if error:
        logger.warning("OAuth denied: %s", error)
        return RedirectResponse(
            url=f"{frontend_base}/#/login?error=access_denied",
            status_code=status.HTTP_302_FOUND,
        )

    # Missing params
    if not code or not state:
        return RedirectResponse(
            url=f"{frontend_base}/#/login?error=invalid_state",
            status_code=status.HTTP_302_FOUND,
        )

    # Validate state (HMAC + expiry)
    if not validate_state(state):
        logger.warning("Invalid or expired OAuth state")
        return RedirectResponse(
            url=f"{frontend_base}/#/login?error=invalid_state",
            status_code=status.HTTP_302_FOUND,
        )

    # Exchange code for access token
    access_token = await exchange_code_for_token(code)
    if not access_token:
        logger.error("Failed to exchange OAuth code for token")
        return RedirectResponse(
            url=f"{frontend_base}/#/login?error=exchange_failed",
            status_code=status.HTTP_302_FOUND,
        )

    # Fetch GitHub user profile
    gh_user = await get_github_user(access_token)
    if not gh_user:
        logger.error("Failed to fetch GitHub user profile")
        return RedirectResponse(
            url=f"{frontend_base}/#/login?error=exchange_failed",
            status_code=status.HTTP_302_FOUND,
        )

    # Upsert user in DB
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.github_id == gh_user["id"])
        )
        user = result.scalar_one_or_none()

        if user:
            # Update existing user
            user.github_login = gh_user["login"]
            user.avatar_url = gh_user.get("avatar_url")
        else:
            # Create new user
            user = User(
                github_id=gh_user["id"],
                github_login=gh_user["login"],
                avatar_url=gh_user.get("avatar_url"),
            )
            session.add(user)

        await session.commit()
        await session.refresh(user)

        # Generate JWT
        token = _build_jwt(user)

    # NOTE: We intentionally do NOT auto-register the OAuth token as a
    # github-models provider key. GitHub OAuth tokens with scope "read:user"
    # cannot access the GitHub Models inference API — a separate Personal
    # Access Token (PAT) with models:read scope is required. Users must
    # add their PAT manually via Settings > Provider Keys.

    return RedirectResponse(
        url=f"{frontend_base}/#/auth/callback?token={token}",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/validate")
async def validate_token(current_user: CurrentUser) -> AuthValidateResponse:
    """Validate the current JWT and return user info."""
    return AuthValidateResponse(
        user=UserInfo(
            github_id=current_user["github_user_id"],
            login=current_user["login"],
            avatar_url=current_user.get("avatar_url"),
        ),
        exp=current_user["exp"],
    )


@router.post("/logout")
async def logout(current_user: CurrentUser) -> dict:
    """Logout endpoint (stateless — client clears token).

    Exists for logging/audit purposes.
    """
    logger.info("User %s logged out", current_user.get("login"))
    return {"status": "ok", "message": "Logged out successfully."}
