"""Tests for Wave 14: Performance — cost estimation, rate limiting, parallel execution."""

import threading
import time

import pytest

from repoforge.performance import (
    BatchExecutor,
    CostEstimate,
    RateLimiter,
    estimate_cost,
)

# ── Cost estimation ──────────────────────────────────────────────────────


class TestCostEstimate:

    def test_estimate_returns_dataclass(self):
        est = estimate_cost(
            chapters=7, avg_input_tokens=3000, avg_output_tokens=2000,
            model="gpt-4o-mini",
        )
        assert isinstance(est, CostEstimate)

    def test_has_total_cost(self):
        est = estimate_cost(chapters=7, avg_input_tokens=3000, avg_output_tokens=2000)
        assert est.total_cost >= 0.0

    def test_more_chapters_costs_more(self):
        small = estimate_cost(chapters=3, avg_input_tokens=2000, avg_output_tokens=1000)
        large = estimate_cost(chapters=10, avg_input_tokens=2000, avg_output_tokens=1000)
        assert large.total_cost > small.total_cost

    def test_includes_token_counts(self):
        est = estimate_cost(chapters=5, avg_input_tokens=3000, avg_output_tokens=2000)
        assert est.total_input_tokens == 5 * 3000
        assert est.total_output_tokens == 5 * 2000

    def test_refinement_multiplier(self):
        base = estimate_cost(chapters=5, avg_input_tokens=3000, avg_output_tokens=2000)
        refined = estimate_cost(
            chapters=5, avg_input_tokens=3000, avg_output_tokens=2000,
            refinement_iterations=3,
        )
        assert refined.total_cost > base.total_cost

    def test_known_model_pricing(self):
        est = estimate_cost(
            chapters=1, avg_input_tokens=1000, avg_output_tokens=1000,
            model="gpt-4o-mini",
        )
        # gpt-4o-mini is cheap — should be under $0.01 for 1 chapter
        assert est.total_cost < 0.01

    def test_unknown_model_uses_default(self):
        est = estimate_cost(
            chapters=1, avg_input_tokens=1000, avg_output_tokens=1000,
            model="unknown-model-xyz",
        )
        assert est.total_cost > 0

    def test_format_output(self):
        est = estimate_cost(chapters=7, avg_input_tokens=3000, avg_output_tokens=2000)
        formatted = est.format()
        assert "$" in formatted
        assert "token" in formatted.lower()


# ── Rate limiter ─────────────────────────────────────────────────────────


class TestRateLimiter:

    def test_allows_within_limit(self):
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        for _ in range(10):
            assert limiter.acquire() is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.acquire() is True
        assert limiter.acquire() is True
        assert limiter.acquire() is False

    def test_tracks_remaining(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.remaining == 5
        limiter.acquire()
        assert limiter.remaining == 4

    def test_resets_after_window(self):
        limiter = RateLimiter(max_requests=1, window_seconds=0.1)
        limiter.acquire()
        assert limiter.acquire() is False
        time.sleep(0.15)
        assert limiter.acquire() is True

    def test_wait_time(self):
        limiter = RateLimiter(max_requests=1, window_seconds=10)
        limiter.acquire()
        wait = limiter.wait_time()
        assert wait > 0
        assert wait <= 10

    def test_acquire_or_wait_blocks_then_acquires(self):
        """Second thread should block until the window expires, then acquire."""
        limiter = RateLimiter(max_requests=1, window_seconds=0.15)
        limiter.acquire()  # exhaust the single slot

        acquired_at = []

        def worker():
            limiter.acquire_or_wait()
            acquired_at.append(time.monotonic())

        start = time.monotonic()
        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=2.0)

        assert len(acquired_at) == 1, "Worker should have acquired a slot"
        elapsed = acquired_at[0] - start
        # Should have waited roughly the window duration
        assert elapsed >= 0.10, f"Expected wait >=0.10s, got {elapsed:.3f}s"

    def test_acquire_or_wait_immediate_when_slot_available(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        start = time.monotonic()
        limiter.acquire_or_wait()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1, "Should acquire immediately when slots available"
        assert limiter.remaining == 4

    def test_thread_safety_concurrent_acquire(self):
        """Concurrent acquire() calls must never exceed max_requests."""
        max_req = 10
        limiter = RateLimiter(max_requests=max_req, window_seconds=60)
        results: list[bool] = []
        lock = threading.Lock()

        def worker():
            result = limiter.acquire()
            with lock:
                results.append(result)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(results) == 20
        acquired = sum(1 for r in results if r)
        assert acquired == max_req, (
            f"Expected exactly {max_req} acquisitions, got {acquired}"
        )


# ── Batch executor ───────────────────────────────────────────────────────


class TestBatchExecutor:

    def test_executes_all_items(self):
        results = []
        def task(item):
            results.append(item * 2)
            return item * 2

        executor = BatchExecutor(max_concurrent=2)
        output = executor.run([1, 2, 3, 4], task)
        assert len(output) == 4
        assert sorted(output) == [2, 4, 6, 8]

    def test_respects_concurrency_limit(self):
        """Verify tasks don't exceed max_concurrent (via sequential fallback)."""
        executor = BatchExecutor(max_concurrent=1)
        output = executor.run([1, 2, 3], lambda x: x + 1)
        assert output == [2, 3, 4]

    def test_empty_input(self):
        executor = BatchExecutor(max_concurrent=4)
        output = executor.run([], lambda x: x)
        assert output == []

    def test_handles_exceptions(self):
        def failing_task(item):
            if item == 2:
                raise ValueError("boom")
            return item

        executor = BatchExecutor(max_concurrent=2)
        output = executor.run([1, 2, 3], failing_task)
        # Should get results for 1 and 3, None for 2
        assert len(output) == 3
        assert 1 in output
        assert 3 in output
        assert None in output
