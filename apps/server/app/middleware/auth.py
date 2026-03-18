"""JWT authentication dependency for FastAPI."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status

from app.config import settings


def _extract_token(request: Request) -> str:
    """Extract Bearer token from Authorization header or ?token= query param.

    Query param fallback is needed for SSE endpoints where EventSource
    does not support custom headers.
    """
    # 1. Try Authorization header first
    auth_header = request.headers.get("Authorization")
    if auth_header:
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() == "bearer" and token:
            return token

    # 2. Fall back to ?token= query param (for SSE / EventSource)
    token = request.query_params.get("token")
    if token:
        return token

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "missing_token", "message": "Authorization header is required."},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(request: Request) -> dict:
    """FastAPI dependency: decode and validate JWT, return user claims.

    Returns a dict with keys: sub, github_user_id, login, avatar_url.
    Raises 401 on missing/invalid/expired tokens.
    """
    token = _extract_token(request)
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "token_expired", "message": "Token has expired. Please log in again."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "message": "Invalid token."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# Annotated type for dependency injection in route handlers
CurrentUser = Annotated[dict, Depends(get_current_user)]
