"""Test fixtures for the RepoForge server test suite.

Sets environment variables BEFORE importing the app to satisfy
pydantic-settings fail-fast validation.
"""

import os
import time

# ── Set test env vars BEFORE any app imports ─────────────────
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-unit-tests")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("STATE_SECRET", "test-state-secret")
os.environ.setdefault(
    "ENCRYPTION_KEY",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
)
os.environ.setdefault("DEBUG", "true")

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    """Use asyncio as the async backend for all tests."""
    return "asyncio"


@pytest_asyncio.fixture
async def client():
    """Async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def valid_token() -> str:
    """Create a valid JWT token for authenticated test requests."""
    now = int(time.time())
    payload = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "github_user_id": 12345,
        "login": "testuser",
        "avatar_url": "https://github.com/testuser.png",
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture
def expired_token() -> str:
    """Create an expired JWT token."""
    now = int(time.time())
    payload = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "github_user_id": 12345,
        "login": "testuser",
        "avatar_url": "",
        "iat": now - 7200,
        "exp": now - 3600,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture
def auth_headers(valid_token: str) -> dict:
    """Authorization headers with a valid Bearer token."""
    return {"Authorization": f"Bearer {valid_token}"}
