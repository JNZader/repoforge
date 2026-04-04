"""Tests for the circuit breaker service."""

import pytest
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


async def _succeed():
    """Simulated successful async operation."""
    return "ok"


async def _fail():
    """Simulated failing async operation."""
    raise RuntimeError("LLM API error")


@pytest.mark.asyncio
async def test_starts_closed():
    """Circuit breaker should start in closed state."""
    cb = CircuitBreaker(threshold=3, reset_timeout_s=1.0)
    state = cb.get_state()
    assert state["state"] == "closed"
    assert state["failures"] == 0


@pytest.mark.asyncio
async def test_successful_call():
    """A successful call should return the result and stay closed."""
    cb = CircuitBreaker(threshold=3, reset_timeout_s=1.0)
    result = await cb.execute(_succeed)
    assert result == "ok"
    assert cb.get_state()["state"] == "closed"


@pytest.mark.asyncio
async def test_failure_increments_counter():
    """Each failure should increment the failure counter."""
    cb = CircuitBreaker(threshold=3, reset_timeout_s=1.0)
    with pytest.raises(RuntimeError):
        await cb.execute(_fail)
    assert cb.get_state()["failures"] == 1
    assert cb.get_state()["state"] == "closed"


@pytest.mark.asyncio
async def test_opens_after_threshold():
    """Circuit should open after reaching threshold failures."""
    cb = CircuitBreaker(threshold=3, reset_timeout_s=1.0)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            await cb.execute(_fail)
    assert cb.get_state()["state"] == "open"


@pytest.mark.asyncio
async def test_open_rejects_calls():
    """Calls should be rejected when circuit is open."""
    cb = CircuitBreaker(threshold=2, reset_timeout_s=60.0)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.execute(_fail)
    with pytest.raises(CircuitBreakerOpenError):
        await cb.execute(_succeed)


@pytest.mark.asyncio
async def test_half_open_after_timeout():
    """Circuit should transition to half-open after reset timeout."""
    import time

    cb = CircuitBreaker(threshold=2, reset_timeout_s=0.1)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.execute(_fail)
    assert cb.get_state()["state"] == "open"

    # Wait for reset timeout
    import asyncio
    await asyncio.sleep(0.15)

    # Next call should go through (half-open)
    result = await cb.execute(_succeed)
    assert result == "ok"
    assert cb.get_state()["state"] == "closed"


@pytest.mark.asyncio
async def test_success_resets_failures():
    """A successful call should reset the failure counter to 0."""
    cb = CircuitBreaker(threshold=5, reset_timeout_s=1.0)
    # Accumulate some failures
    for _ in range(3):
        with pytest.raises(RuntimeError):
            await cb.execute(_fail)
    assert cb.get_state()["failures"] == 3

    # Success should reset
    result = await cb.execute(_succeed)
    assert result == "ok"
    assert cb.get_state()["failures"] == 0
