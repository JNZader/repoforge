"""Tests for Wave 14: Performance — cost estimation, rate limiting, parallel execution."""

import time

import pytest

from repoforge.performance import (
    estimate_cost,
    CostEstimate,
    RateLimiter,
    BatchExecutor,
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
