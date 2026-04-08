"""Performance utilities — cost estimation, rate limiting, batch execution.

Usage:
    from repoforge.performance import estimate_cost, RateLimiter, BatchExecutor

    # Cost estimation before generating
    est = estimate_cost(chapters=7, avg_input_tokens=3000, avg_output_tokens=2000)
    print(est.format())  # "Estimated cost: $0.04 (35K tokens)"

    # Rate limiting for API calls
    limiter = RateLimiter(max_requests=50, window_seconds=60)
    if limiter.acquire():
        llm.complete(...)

    # Batch execution with concurrency control
    executor = BatchExecutor(max_concurrent=4)
    results = executor.run(chapters, generate_chapter)
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model pricing (per 1M tokens, USD)
# ---------------------------------------------------------------------------

_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "claude-haiku-3-5": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-opus-4": {"input": 15.00, "output": 75.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "_default": {"input": 1.00, "output": 5.00},
}


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


@dataclass
class CostEstimate:
    """Estimated cost for a documentation generation run."""

    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    model: str
    chapters: int
    refinement_iterations: int = 1

    def format(self) -> str:
        total_tokens = self.total_input_tokens + self.total_output_tokens
        if total_tokens >= 1_000_000:
            token_str = f"{total_tokens / 1_000_000:.1f}M tokens"
        elif total_tokens >= 1_000:
            token_str = f"{total_tokens / 1_000:.0f}K tokens"
        else:
            token_str = f"{total_tokens} tokens"

        return (
            f"Estimated cost: ${self.total_cost:.4f} "
            f"({token_str}, {self.chapters} chapters"
            f"{f', {self.refinement_iterations}x refinement' if self.refinement_iterations > 1 else ''})"
        )


def estimate_cost(
    chapters: int,
    avg_input_tokens: int = 3000,
    avg_output_tokens: int = 2000,
    model: str = "_default",
    refinement_iterations: int = 1,
) -> CostEstimate:
    """Estimate the cost of generating documentation.

    Args:
        chapters: Number of chapters to generate.
        avg_input_tokens: Average input tokens per chapter prompt.
        avg_output_tokens: Average output tokens per chapter.
        model: LLM model name for pricing lookup.
        refinement_iterations: Number of refinement passes (1 = no refinement).
    """
    # Lookup pricing — try exact match, then prefix match, then default
    pricing = _PRICING.get(model)
    if pricing is None:
        for key in _PRICING:
            if model.startswith(key.split("-")[0]):
                pricing = _PRICING[key]
                break
    if pricing is None:
        pricing = _PRICING["_default"]

    total_calls = chapters * refinement_iterations
    total_input = total_calls * avg_input_tokens
    total_output = total_calls * avg_output_tokens

    cost = (
        (total_input / 1_000_000) * pricing["input"]
        + (total_output / 1_000_000) * pricing["output"]
    )

    return CostEstimate(
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_cost=round(cost, 6),
        model=model,
        chapters=chapters,
        refinement_iterations=refinement_iterations,
    )


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Thread-safe sliding-window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    def _prune(self) -> None:
        """Remove expired timestamps. Caller MUST hold ``self._lock``."""
        now = time.monotonic()
        cutoff = now - self._window
        self._timestamps = [t for t in self._timestamps if t > cutoff]

    def acquire(self) -> bool:
        """Try to acquire a request slot. Returns False if rate limited."""
        with self._lock:
            self._prune()
            if len(self._timestamps) >= self._max:
                return False
            self._timestamps.append(time.monotonic())
            return True

    def acquire_or_wait(self) -> None:
        """Block until a request slot is available, then acquire it."""
        while True:
            with self._lock:
                self._prune()
                if len(self._timestamps) < self._max:
                    self._timestamps.append(time.monotonic())
                    return
                wait = self._timestamps[0] + self._window - time.monotonic()
            time.sleep(max(0.01, wait))

    @property
    def remaining(self) -> int:
        with self._lock:
            self._prune()
            return max(0, self._max - len(self._timestamps))

    def wait_time(self) -> float:
        """Seconds until the next slot is available. 0 if available now."""
        with self._lock:
            self._prune()
            if len(self._timestamps) < self._max:
                return 0.0
            oldest = self._timestamps[0]
            return max(0.0, oldest + self._window - time.monotonic())


# ---------------------------------------------------------------------------
# Batch executor
# ---------------------------------------------------------------------------


class BatchExecutor:
    """Execute tasks with controlled concurrency."""

    def __init__(self, max_concurrent: int = 4) -> None:
        self._max = max_concurrent

    def run(self, items: list, task_fn, **kwargs) -> list:
        """Run task_fn on each item with concurrency control.

        Returns results in the same order as items.
        Failed tasks return None.
        """
        if not items:
            return []

        if self._max <= 1:
            return self._run_sequential(items, task_fn)

        return self._run_parallel(items, task_fn)

    def _run_sequential(self, items: list, task_fn) -> list:
        results = []
        for item in items:
            try:
                results.append(task_fn(item))
            except Exception as e:
                logger.warning("Task failed: %s", e)
                results.append(None)
        return results

    def _run_parallel(self, items: list, task_fn) -> list:
        results = [None] * len(items)
        with ThreadPoolExecutor(max_workers=self._max) as pool:
            futures = {pool.submit(task_fn, item): i for i, item in enumerate(items)}
            for future in futures:
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.warning("Task %d failed: %s", idx, e)
        return results
