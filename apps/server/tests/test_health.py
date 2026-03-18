"""Tests for health check endpoints."""

import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    """GET /health should return 200 with status ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_detailed_returns_200(client):
    """GET /health/detailed should return 200 with system status."""
    response = await client.get("/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert "circuit_breaker" in data
    assert "active_generations" in data
    assert "response_ms" in data
