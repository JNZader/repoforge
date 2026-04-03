"""Rate limiting configuration using slowapi.

Three tiers:
  - auth:     10/minute per IP (login, callback)
  - api:      100/minute per user_id (general API endpoints)
  - generate: 20/hour per user_id (generation-heavy endpoint)

Rate limit headers (X-RateLimit-Limit, X-RateLimit-Remaining,
X-RateLimit-Reset) are automatically added by slowapi.

Usage in routes:
    from app.middleware.rate_limit import limiter

    @router.get("/something")
    @limiter.limit("100/minute", key_func=get_user_id_key)
    async def something(request: Request, ...): ...
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings


def get_user_id_key(request: Request) -> str:
    """Extract user_id from JWT claims for per-user rate limiting.

    Falls back to IP address if no JWT is present (shouldn't happen
    on authenticated endpoints, but fail-safe).
    """
    # The JWT is decoded in get_current_user dependency — we need to
    # extract the sub claim directly for the rate limiter key function.
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        import jwt as pyjwt

        token = auth_header.split(" ", 1)[1]
        try:
            payload = pyjwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False},  # Don't fail on expiry for key extraction
            )
            return payload.get("sub", get_remote_address(request))
        except (pyjwt.InvalidTokenError, KeyError, ValueError):
            pass  # Invalid/expired/malformed JWT — fall through to IP-based key

    # Fall back to query param token (SSE endpoints)
    token = request.query_params.get("token")
    if token:
        import jwt as pyjwt

        try:
            payload = pyjwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            return payload.get("sub", get_remote_address(request))
        except (pyjwt.InvalidTokenError, KeyError, ValueError):
            pass  # Invalid/expired/malformed JWT — fall through to IP-based key

    return get_remote_address(request)


# Create the limiter instance — in-memory storage for single-instance deployment.
# Can be swapped to Redis backend for multi-instance scaling.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
)

# Pre-built limit strings from settings
AUTH_LIMIT = f"{settings.RATE_LIMIT_AUTH_PER_MINUTE}/minute"
API_LIMIT = f"{settings.RATE_LIMIT_API_PER_MINUTE}/minute"
GENERATE_LIMIT = f"{settings.RATE_LIMIT_GENERATE_PER_HOUR}/hour"
