"""GitHub OAuth helper functions.

Handles state generation/validation, code-to-token exchange, and user info retrieval.
"""

import hashlib
import hmac
import time

import httpx

from app.config import settings

# --- State parameter (CSRF protection) ---

_STATE_MAX_AGE_SECONDS = 300  # 5 minutes


def _base36_encode(number: int) -> str:
    """Encode an integer as base36 string."""
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if number == 0:
        return "0"
    result = []
    while number:
        number, remainder = divmod(number, 36)
        result.append(chars[remainder])
    return "".join(reversed(result))


def _base36_decode(s: str) -> int:
    """Decode a base36 string to integer."""
    return int(s, 36)


def generate_state() -> str:
    """Generate an HMAC-signed state parameter.

    Format: ``{timestamp_base36}.{hmac_sha256_hex}``
    """
    ts = int(time.time())
    ts_b36 = _base36_encode(ts)
    signature = hmac.new(
        settings.STATE_SECRET.encode(),
        ts_b36.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{ts_b36}.{signature}"


def validate_state(state: str) -> bool:
    """Validate HMAC signature and check expiry (5 min) of a state parameter."""
    parts = state.split(".", maxsplit=1)
    if len(parts) != 2:
        return False
    ts_b36, provided_sig = parts
    try:
        ts = _base36_decode(ts_b36)
    except ValueError:
        return False
    # Check expiry
    if time.time() - ts > _STATE_MAX_AGE_SECONDS:
        return False
    # Verify HMAC
    expected_sig = hmac.new(
        settings.STATE_SECRET.encode(),
        ts_b36.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(provided_sig, expected_sig)


# --- GitHub API interactions ---

_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"


async def exchange_code_for_token(code: str) -> str | None:
    """Exchange an OAuth authorization code for an access token.

    Returns the access_token string, or None on failure.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _GITHUB_TOKEN_URL,
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data.get("access_token")


async def get_github_user(access_token: str) -> dict | None:
    """Fetch user profile from GitHub API.

    Returns a dict with id, login, avatar_url, etc., or None on failure.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            _GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        if resp.status_code != 200:
            return None
        return resp.json()
