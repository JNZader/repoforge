"""Tests for Wave 6: Refinement loop (generate → score → critique → regen)."""

import pytest

from repoforge.refinement import refine_chapter, RefinementResult


GOOD_CONTENT = """# Architecture

## Overview

The system uses a layered architecture with clear separation.

## Components

| Component | Purpose | File |
|-----------|---------|------|
| API | HTTP | `server.py` |
| Store | Data | `store.py` |

## Data Flow

```mermaid
graph LR
    Client --> API --> Store
```

## Decisions

- **SQLite**: Embedded, zero-config.
- **HTTP**: Standard protocol.

```python
def handle_request(req):
    return Response(200)
```
"""

WEAK_CONTENT = """# Overview

This is a project. It does stuff.
"""


class FakeLLM:
    """Mock LLM that improves content on each call."""

    def __init__(self, responses=None):
        self._responses = responses or [GOOD_CONTENT]
        self._call_count = 0

    def complete(self, prompt, system=None):
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        return self._responses[idx]

    @property
    def call_count(self):
        return self._call_count


# ── RefinementResult dataclass ───────────────────────────────────────────


class TestRefinementResult:

    def test_fields(self):
        r = RefinementResult(
            final_content="# Test", iterations=2,
            score_progression=[0.3, 0.8], converged=True,
        )
        assert r.iterations == 2
        assert r.converged is True
        assert len(r.score_progression) == 2


# ── refine_chapter ───────────────────────────────────────────────────────


class TestRefineChapter:

    def _chapter(self):
        return {
            "file": "03-architecture.md",
            "title": "Architecture",
            "system": "You are a tech writer.",
            "user": "Generate architecture docs.",
        }

    def test_returns_refinement_result(self):
        llm = FakeLLM([GOOD_CONTENT])
        result = refine_chapter(llm, self._chapter())
        assert isinstance(result, RefinementResult)
        assert result.final_content.strip() != ""

    def test_good_content_converges_in_one_iteration(self):
        llm = FakeLLM([GOOD_CONTENT])
        result = refine_chapter(llm, self._chapter(), threshold=0.5)
        assert result.iterations == 1
        assert result.converged is True

    def test_weak_content_triggers_refinement(self):
        # First call returns weak, second returns good
        llm = FakeLLM([WEAK_CONTENT, GOOD_CONTENT])
        result = refine_chapter(llm, self._chapter(), threshold=0.5, max_iterations=3)
        assert result.iterations >= 2
        assert llm.call_count >= 2

    def test_max_iterations_caps_loop(self):
        # Always returns weak content — should stop at max
        llm = FakeLLM([WEAK_CONTENT] * 10)
        result = refine_chapter(llm, self._chapter(), threshold=0.99, max_iterations=3)
        assert result.iterations == 3
        assert result.converged is False
        assert llm.call_count == 3

    def test_score_progression_recorded(self):
        llm = FakeLLM([WEAK_CONTENT, GOOD_CONTENT])
        result = refine_chapter(llm, self._chapter(), threshold=0.5, max_iterations=3)
        assert len(result.score_progression) == result.iterations
        assert all(isinstance(s, float) for s in result.score_progression)

    def test_threshold_zero_always_converges(self):
        llm = FakeLLM([WEAK_CONTENT])
        result = refine_chapter(llm, self._chapter(), threshold=0.0)
        assert result.iterations == 1
        assert result.converged is True

    def test_default_max_iterations(self):
        llm = FakeLLM([WEAK_CONTENT] * 10)
        result = refine_chapter(llm, self._chapter(), threshold=0.99)
        # Default max should be reasonable (3)
        assert result.iterations <= 3

    def test_critique_included_in_refinement_prompt(self):
        """The refinement prompt should include score feedback."""
        prompts_sent = []

        class CaptureLLM:
            def complete(self, prompt, system=None):
                prompts_sent.append(prompt)
                return WEAK_CONTENT

        llm = CaptureLLM()
        refine_chapter(llm, self._chapter(), threshold=0.99, max_iterations=2)
        # Second call should reference the score/feedback
        assert len(prompts_sent) == 2
        assert "score" in prompts_sent[1].lower() or "improve" in prompts_sent[1].lower()
