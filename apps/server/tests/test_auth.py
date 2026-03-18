"""Tests for authentication endpoints."""

import pytest


@pytest.mark.asyncio
async def test_login_redirects_to_github(client):
    """GET /auth/login should redirect to GitHub OAuth."""
    response = await client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert "github.com/login/oauth/authorize" in location
    assert "client_id=" in location


@pytest.mark.asyncio
async def test_validate_with_no_token_returns_401(client):
    """POST /auth/validate without a token should return 401."""
    response = await client.post("/auth/validate")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_validate_with_invalid_token_returns_401(client):
    """POST /auth/validate with an invalid token should return 401."""
    response = await client.post(
        "/auth/validate",
        headers={"Authorization": "Bearer totally-invalid-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_validate_with_expired_token_returns_401(client, expired_token):
    """POST /auth/validate with an expired token should return 401."""
    response = await client.post(
        "/auth/validate",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_validate_with_valid_token_returns_user(client, valid_token):
    """POST /auth/validate with a valid JWT should return user info."""
    response = await client.post(
        "/auth/validate",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["login"] == "testuser"
    assert data["user"]["github_id"] == 12345
    assert "exp" in data
