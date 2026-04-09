"""Unit tests for cost-weighted routing in repoforge.model_router."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from repoforge.model_router import (
    COST_WEIGHTS,
    DEFAULT_COST_WEIGHT,
    ModelRouter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_build_llm(model=None, api_key=None, api_base=None):
    provider = MagicMock()
    provider.model = model or "auto-detected"
    return provider


# ---------------------------------------------------------------------------
# _resolve_cost_weight
# ---------------------------------------------------------------------------

class TestResolveCostWeight:
    """Verify substring matching logic and default fallback."""

    def test_known_models(self):
        assert ModelRouter._resolve_cost_weight("claude-haiku-3-5") == 1
        assert ModelRouter._resolve_cost_weight("claude-sonnet-4") == 5
        assert ModelRouter._resolve_cost_weight("claude-opus-4") == 25

    def test_openai_models(self):
        assert ModelRouter._resolve_cost_weight("gpt-4o-mini") == 1
        assert ModelRouter._resolve_cost_weight("gpt-4o") == 10
        assert ModelRouter._resolve_cost_weight("gpt-4.1-mini") == 1
        assert ModelRouter._resolve_cost_weight("gpt-4.1-nano") == 1
        assert ModelRouter._resolve_cost_weight("gpt-4.1") == 10

    def test_google_models(self):
        assert ModelRouter._resolve_cost_weight("gemini-flash-2.0") == 1
        assert ModelRouter._resolve_cost_weight("gemini-2.0-flash-exp") == 1
        assert ModelRouter._resolve_cost_weight("gemini-pro-1.5") == 5

    def test_budget_models(self):
        assert ModelRouter._resolve_cost_weight("deepseek-v3") == 1
        assert ModelRouter._resolve_cost_weight("llama-3.1-70b") == 1
        assert ModelRouter._resolve_cost_weight("mistral-large") == 2
        assert ModelRouter._resolve_cost_weight("mixtral-8x7b") == 3

    def test_unknown_model_returns_default(self):
        assert ModelRouter._resolve_cost_weight("some-unknown-model") == DEFAULT_COST_WEIGHT

    def test_none_model_returns_default(self):
        assert ModelRouter._resolve_cost_weight(None) == DEFAULT_COST_WEIGHT

    def test_case_insensitive(self):
        assert ModelRouter._resolve_cost_weight("Claude-Haiku-3-5") == 1
        assert ModelRouter._resolve_cost_weight("GPT-4O-MINI") == 1

    def test_specific_before_broad(self):
        """gpt-4o-mini (1) must match before gpt-4o (10)."""
        assert ModelRouter._resolve_cost_weight("gpt-4o-mini") == 1
        assert ModelRouter._resolve_cost_weight("gpt-4.1-mini") == 1
        assert ModelRouter._resolve_cost_weight("gpt-4.1-nano") == 1


# ---------------------------------------------------------------------------
# get_cost_weight
# ---------------------------------------------------------------------------

class TestGetCostWeight:

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_heavy_chapter_weight(self, mock_build):
        router = ModelRouter(
            models_cfg={"heavy": "claude-opus-4", "standard": "claude-sonnet-4", "light": "claude-haiku-3-5"},
        )
        assert router.get_cost_weight("03-architecture.md") == 25

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_standard_chapter_weight(self, mock_build):
        router = ModelRouter(
            models_cfg={"heavy": "claude-opus-4", "standard": "claude-sonnet-4", "light": "claude-haiku-3-5"},
        )
        assert router.get_cost_weight("05-data-models.md") == 5

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_light_chapter_weight(self, mock_build):
        router = ModelRouter(
            models_cfg={"heavy": "claude-opus-4", "standard": "claude-sonnet-4", "light": "claude-haiku-3-5"},
        )
        assert router.get_cost_weight("index.md") == 1

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_single_model_all_same_weight(self, mock_build):
        router = ModelRouter(
            models_cfg={"heavy": "gpt-4o-mini", "standard": "gpt-4o-mini", "light": "gpt-4o-mini"},
        )
        assert router.get_cost_weight("03-architecture.md") == 1
        assert router.get_cost_weight("05-data-models.md") == 1
        assert router.get_cost_weight("index.md") == 1


# ---------------------------------------------------------------------------
# estimate_total_cost
# ---------------------------------------------------------------------------

class TestEstimateTotalCost:

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_mixed_tiers(self, mock_build):
        router = ModelRouter(
            models_cfg={"heavy": "claude-opus-4", "standard": "claude-sonnet-4", "light": "claude-haiku-3-5"},
        )
        chapters = [
            {"file": "03-architecture.md", "title": "Architecture"},
            {"file": "04-core-mechanisms.md", "title": "Core"},
            {"file": "05-data-models.md", "title": "Data"},
            {"file": "06-api-reference.md", "title": "API"},
            {"file": "index.md", "title": "Index"},
        ]
        result = router.estimate_total_cost(chapters)

        assert result["breakdown"]["heavy"]["count"] == 2
        assert result["breakdown"]["heavy"]["weight"] == 25
        assert result["breakdown"]["heavy"]["subtotal"] == 50
        assert result["breakdown"]["standard"]["count"] == 2
        assert result["breakdown"]["standard"]["weight"] == 5
        assert result["breakdown"]["standard"]["subtotal"] == 10
        assert result["breakdown"]["light"]["count"] == 1
        assert result["breakdown"]["light"]["weight"] == 1
        assert result["breakdown"]["light"]["subtotal"] == 1
        assert result["total"] == 61

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_display_string_format(self, mock_build):
        router = ModelRouter(
            models_cfg={"heavy": "claude-sonnet-4", "standard": "claude-sonnet-4", "light": "claude-haiku-3-5"},
        )
        chapters = [
            {"file": "03-architecture.md", "title": "Arch"},
            {"file": "index.md", "title": "Index"},
        ]
        result = router.estimate_total_cost(chapters)
        assert "Estimated relative cost:" in result["display"]
        assert str(result["total"]) in result["display"]

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_empty_chapters(self, mock_build):
        router = ModelRouter(
            models_cfg={"heavy": "claude-opus-4", "standard": "claude-sonnet-4", "light": "claude-haiku-3-5"},
        )
        result = router.estimate_total_cost([])
        assert result["total"] == 0
        assert result["breakdown"] == {}

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_single_model_uniform_cost(self, mock_build):
        router = ModelRouter(
            models_cfg={"heavy": "gpt-4o-mini", "standard": "gpt-4o-mini", "light": "gpt-4o-mini"},
        )
        chapters = [
            {"file": "03-architecture.md", "title": "A"},
            {"file": "05-data-models.md", "title": "B"},
            {"file": "index.md", "title": "C"},
        ]
        result = router.estimate_total_cost(chapters)
        # All tiers use gpt-4o-mini (weight=1), so total = 3
        assert result["total"] == 3

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_unknown_model_uses_default_weight(self, mock_build):
        router = ModelRouter(
            models_cfg={"heavy": "mystery-llm", "standard": "mystery-llm", "light": "mystery-llm"},
        )
        chapters = [{"file": "03-architecture.md", "title": "A"}]
        result = router.estimate_total_cost(chapters)
        assert result["total"] == DEFAULT_COST_WEIGHT
