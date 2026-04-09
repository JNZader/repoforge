"""Unit tests for repoforge.model_router — Smart Model Router."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from repoforge.model_router import TIER_MAP, ModelRouter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_build_llm(model=None, api_key=None, api_base=None):
    """Return a mock whose ``.model`` matches the requested model string."""
    provider = MagicMock()
    provider.model = model or "auto-detected"
    return provider


def _failing_build_llm_for(failing_model: str):
    """Return a build_llm that raises for *failing_model* but works for others."""
    def _build(model=None, api_key=None, api_base=None):
        if model == failing_model:
            raise RuntimeError(f"Cannot init {model}")
        return _fake_build_llm(model=model, api_key=api_key, api_base=api_base)
    return _build


# ---------------------------------------------------------------------------
# Phase 1: Tier resolution
# ---------------------------------------------------------------------------

class TestTierResolution:
    """Verify TIER_MAP lookups and defaults."""

    def test_heavy_chapters(self):
        router = self._single_model_router()
        assert router.get_tier("03-architecture.md") == "heavy"
        assert router.get_tier("04-core-mechanisms.md") == "heavy"

    def test_light_chapters(self):
        router = self._single_model_router()
        assert router.get_tier("index.md") == "light"
        assert router.get_tier("02-quickstart.md") == "light"
        assert router.get_tier("07-dev-guide.md") == "light"

    def test_standard_chapters(self):
        router = self._single_model_router()
        for fname in ("01-overview.md", "05-data-models.md", "06-api-reference.md"):
            assert router.get_tier(fname) == "standard"

    def test_unknown_chapter_defaults_to_standard(self):
        router = self._single_model_router()
        assert router.get_tier("99-custom.md") == "standard"
        assert router.get_tier("totally-new.md") == "standard"

    def test_subdir_prefix_stripping(self):
        """Chapters may come as 'some-subdir/03-architecture.md'."""
        router = self._single_model_router()
        assert router.get_tier("api/03-architecture.md") == "heavy"
        assert router.get_tier("guides/02-quickstart.md") == "light"
        assert router.get_tier("nested/deep/index.md") == "light"

    # helper
    @staticmethod
    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def _single_model_router(mock_build=None):
        return ModelRouter(
            models_cfg={"heavy": "m-heavy", "standard": "m-std", "light": "m-light"},
        )


# ---------------------------------------------------------------------------
# Phase 1: LLM caching
# ---------------------------------------------------------------------------

class TestLLMCaching:
    """Verify that same model string returns same provider instance."""

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_same_model_reuses_provider(self, mock_build):
        """When all tiers use the same model, build_llm is called once."""
        router = ModelRouter(
            models_cfg={"heavy": "shared", "standard": "shared", "light": "shared"},
        )
        p1 = router.get_llm_for_chapter("03-architecture.md")
        p2 = router.get_llm_for_chapter("index.md")
        p3 = router.get_llm_for_chapter("05-data-models.md")
        assert p1 is p2 is p3
        # build_llm called only once for "shared"
        assert mock_build.call_count == 1

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_different_models_get_different_providers(self, mock_build):
        router = ModelRouter(
            models_cfg={"heavy": "m-heavy", "standard": "m-std", "light": "m-light"},
        )
        p_heavy = router.get_llm_for_chapter("03-architecture.md")
        p_std = router.get_llm_for_chapter("05-data-models.md")
        p_light = router.get_llm_for_chapter("index.md")
        assert p_heavy is not p_std
        assert p_std is not p_light
        assert mock_build.call_count == 3


# ---------------------------------------------------------------------------
# Phase 1: from_config factory
# ---------------------------------------------------------------------------

class TestFromConfig:
    """Test ModelRouter.from_config with auto vs single model."""

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_single_model_mode(self, mock_build):
        """Non-auto model wraps the same model in all tiers."""
        router = ModelRouter.from_config(model="gpt-4o-mini")
        assert not router.is_multi_model
        p1 = router.get_llm_for_chapter("03-architecture.md")
        p2 = router.get_llm_for_chapter("index.md")
        assert p1 is p2

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_auto_mode_with_config(self, mock_build):
        """Auto mode reads per-tier models from config dict."""
        cfg = {
            "models": {
                "heavy": "claude-sonnet-4",
                "standard": "gpt-4o-mini",
                "light": "claude-haiku-3-5",
            }
        }
        router = ModelRouter.from_config(model="auto", config=cfg)
        assert router.is_multi_model
        # Heavy chapter should get claude-sonnet-4
        p = router.get_llm_for_chapter("03-architecture.md")
        assert p.model == "claude-sonnet-4"

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_cli_overrides_win_over_config(self, mock_build):
        """CLI --model-heavy overrides yaml config."""
        cfg = {"models": {"heavy": "yaml-heavy", "standard": "yaml-std", "light": "yaml-light"}}
        overrides = {"heavy": "cli-heavy"}
        router = ModelRouter.from_config(model="auto", config=cfg, cli_overrides=overrides)
        p = router.get_llm_for_chapter("03-architecture.md")
        assert p.model == "cli-heavy"
        # Standard still comes from config
        p_std = router.get_llm_for_chapter("05-data-models.md")
        assert p_std.model == "yaml-std"

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_none_model_auto_detects(self, mock_build):
        """model=None (default) passes None to build_llm for auto-detection."""
        router = ModelRouter.from_config(model=None)
        p = router.get_llm_for_chapter("index.md")
        # build_llm receives model=None and returns auto-detected
        assert p.model == "auto-detected"


# ---------------------------------------------------------------------------
# Phase 1: Fallback on init failure
# ---------------------------------------------------------------------------

class TestFallback:
    """Verify graceful degradation when a tier's model fails to init."""

    @patch("repoforge.model_router.build_llm")
    def test_heavy_falls_back_to_standard(self, mock_build):
        mock_build.side_effect = _failing_build_llm_for("bad-heavy")
        router = ModelRouter(
            models_cfg={"heavy": "bad-heavy", "standard": "good-std", "light": "good-light"},
        )
        # Heavy chapter now uses standard model
        p = router.get_llm_for_chapter("03-architecture.md")
        assert p.model == "good-std"

    @patch("repoforge.model_router.build_llm")
    def test_standard_falls_back_to_light(self, mock_build):
        mock_build.side_effect = _failing_build_llm_for("bad-std")
        router = ModelRouter(
            models_cfg={"heavy": "good-heavy", "standard": "bad-std", "light": "good-light"},
        )
        p = router.get_llm_for_chapter("05-data-models.md")
        assert p.model == "good-light"

    @patch("repoforge.model_router.build_llm")
    def test_light_failure_raises(self, mock_build):
        """Light is the last tier — no fallback, must raise."""
        mock_build.side_effect = _failing_build_llm_for("bad-light")
        with pytest.raises(RuntimeError, match="Cannot init bad-light"):
            ModelRouter(
                models_cfg={"heavy": "good", "standard": "good", "light": "bad-light"},
            )


# ---------------------------------------------------------------------------
# Phase 1: is_multi_model property
# ---------------------------------------------------------------------------

class TestIsMultiModel:

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_multi_model_true(self, mock_build):
        router = ModelRouter(
            models_cfg={"heavy": "a", "standard": "b", "light": "c"},
        )
        assert router.is_multi_model is True

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_single_model_false(self, mock_build):
        router = ModelRouter(
            models_cfg={"heavy": "same", "standard": "same", "light": "same"},
        )
        assert router.is_multi_model is False

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_two_distinct_is_multi(self, mock_build):
        router = ModelRouter(
            models_cfg={"heavy": "a", "standard": "a", "light": "b"},
        )
        assert router.is_multi_model is True


# ---------------------------------------------------------------------------
# Per-chapter model/tier overrides
# ---------------------------------------------------------------------------

class TestModelOverride:
    """Verify model_override and tier_override in get_llm_for_chapter."""

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_model_override_bypasses_tier_map(self, mock_build):
        """model_override builds an ad-hoc provider, ignoring TIER_MAP."""
        router = ModelRouter(
            models_cfg={"heavy": "m-heavy", "standard": "m-std", "light": "m-light"},
        )
        # index.md is normally "light" tier
        p = router.get_llm_for_chapter("index.md", model_override="gpt-4o")
        assert p.model == "gpt-4o"

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_model_override_is_cached(self, mock_build):
        """Same model_override string reuses the cached provider."""
        router = ModelRouter(
            models_cfg={"heavy": "m-heavy", "standard": "m-std", "light": "m-light"},
        )
        p1 = router.get_llm_for_chapter("index.md", model_override="gpt-4o")
        p2 = router.get_llm_for_chapter("03-architecture.md", model_override="gpt-4o")
        assert p1 is p2

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_tier_override_uses_specified_tier(self, mock_build):
        """tier_override resolves to that tier's model instead of TIER_MAP."""
        router = ModelRouter(
            models_cfg={"heavy": "m-heavy", "standard": "m-std", "light": "m-light"},
        )
        # index.md is normally "light", but we override to "heavy"
        p = router.get_llm_for_chapter("index.md", tier_override="heavy")
        assert p.model == "m-heavy"

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_model_override_wins_over_tier_override(self, mock_build):
        """When both are set, model_override takes precedence."""
        router = ModelRouter(
            models_cfg={"heavy": "m-heavy", "standard": "m-std", "light": "m-light"},
        )
        p = router.get_llm_for_chapter(
            "index.md",
            model_override="explicit-model",
            tier_override="heavy",
        )
        assert p.model == "explicit-model"

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_no_overrides_uses_tier_map(self, mock_build):
        """Without overrides, behavior is unchanged (TIER_MAP lookup)."""
        router = ModelRouter(
            models_cfg={"heavy": "m-heavy", "standard": "m-std", "light": "m-light"},
        )
        p = router.get_llm_for_chapter("03-architecture.md")
        assert p.model == "m-heavy"
        p2 = router.get_llm_for_chapter("index.md")
        assert p2.model == "m-light"

    @patch("repoforge.model_router.build_llm", side_effect=_fake_build_llm)
    def test_tier_override_unconfigured_raises(self, mock_build):
        """tier_override with a tier not in config raises ValueError."""
        router = ModelRouter(
            models_cfg={"heavy": "m-heavy", "standard": "m-std", "light": "m-light"},
        )
        with pytest.raises(ValueError, match="No model configured for tier 'ultra'"):
            router.get_llm_for_chapter("index.md", tier_override="ultra")
