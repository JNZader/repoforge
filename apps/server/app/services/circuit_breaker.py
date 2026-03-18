"""Simple circuit breaker for external API calls.

States: closed (normal) → open (fail-fast) → half-open (probe).
Opens after `threshold` consecutive failures.
Resets to closed after a successful call in half-open state.
Transitions from open to half-open after `reset_timeout_s` seconds.
"""

from __future__ import annotations

import time
from typing import Any, TypeVar

T = TypeVar("T")


class CircuitBreakerOpenError(Exception):
    """Raised when a call is attempted while the circuit breaker is open."""


class CircuitBreaker:
    """Circuit breaker protecting LLM API calls from cascading failures.

    Usage::

        cb = CircuitBreaker(threshold=5, reset_timeout_s=30.0)
        result = await cb.execute(some_async_fn, arg1, key=val)
    """

    def __init__(self, threshold: int = 5, reset_timeout_s: float = 30.0) -> None:
        self._threshold = threshold
        self._reset_timeout_s = reset_timeout_s
        self._failures = 0
        self._last_failure: float = 0.0
        self._state: str = "closed"  # closed | open | half-open

    async def execute(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute ``fn(*args, **kwargs)`` through the circuit breaker.

        ``fn`` must be an awaitable (async callable).

        Raises:
            CircuitBreakerOpenError: If the circuit is open and the
                reset timeout has not elapsed.
        """
        if self._state == "open":
            if time.monotonic() - self._last_failure > self._reset_timeout_s:
                self._state = "half-open"
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open — {self._failures} consecutive failures. "
                    f"Retry after {self._reset_timeout_s}s."
                )

        try:
            result = await fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Reset failure counter and close the circuit."""
        self._failures = 0
        self._state = "closed"

    def _on_failure(self) -> None:
        """Increment failure counter; open the circuit if threshold is reached."""
        self._failures += 1
        self._last_failure = time.monotonic()
        if self._failures >= self._threshold:
            self._state = "open"

    def get_state(self) -> dict:
        """Return circuit breaker state for health endpoints."""
        return {
            "state": self._state,
            "failures": self._failures,
            "threshold": self._threshold,
            "reset_timeout_s": self._reset_timeout_s,
        }
