"""Integration tests for the smart model router wired into docs_generator + CLI."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(name: str) -> MagicMock:
    """Create a mock LLMProvider with a distinguishable .model attribute."""
    p = MagicMock()
    p.model = name
    p.complete.return_value = f"# Chapter from {name}\n\nContent.\n"
    return p


def _build_llm_dispatch(mapping: dict[str | None, MagicMock]):
    """Return a build_llm side_effect that returns providers from *mapping*."""
    def _build(model=None, api_key=None, api_base=None):
        if model in mapping:
            return mapping[model]
        # Fallback: return a generic mock
        p = MagicMock()
        p.model = model or "auto-detected"
        p.complete.return_value = "# Fallback\n\nContent.\n"
        return p
    return _build


# ---------------------------------------------------------------------------
# Integration: ModelRouter resolves different models per chapter
# ---------------------------------------------------------------------------

class TestAutoModelRouting:
    """--model auto with full tier config resolves different models per chapter."""

    @patch("repoforge.model_router.build_llm")
    def test_auto_routes_chapters_to_correct_tiers(self, mock_build):
        heavy_prov = _make_provider("claude-sonnet-4")
        std_prov = _make_provider("gpt-4o-mini")
        light_prov = _make_provider("claude-haiku-3-5")

        mock_build.side_effect = _build_llm_dispatch({
            "claude-sonnet-4": heavy_prov,
            "gpt-4o-mini": std_prov,
            "claude-haiku-3-5": light_prov,
        })

        from repoforge.model_router import ModelRouter

        cfg = {
            "models": {
                "heavy": "claude-sonnet-4",
                "standard": "gpt-4o-mini",
                "light": "claude-haiku-3-5",
            }
        }
        router = ModelRouter.from_config(model="auto", config=cfg)

        # Heavy chapters
        assert router.get_llm_for_chapter("03-architecture.md") is heavy_prov
        assert router.get_llm_for_chapter("04-core-mechanisms.md") is heavy_prov

        # Light chapters
        assert router.get_llm_for_chapter("index.md") is light_prov
        assert router.get_llm_for_chapter("02-quickstart.md") is light_prov

        # Standard chapters (default)
        assert router.get_llm_for_chapter("05-data-models.md") is std_prov
        assert router.get_llm_for_chapter("01-overview.md") is std_prov


class TestSingleModelMode:
    """Explicit --model (non-auto) uses same provider for all chapters."""

    @patch("repoforge.model_router.build_llm")
    def test_single_model_all_same_provider(self, mock_build):
        single_prov = _make_provider("claude-haiku-3-5")
        mock_build.side_effect = _build_llm_dispatch({
            "claude-haiku-3-5": single_prov,
        })

        from repoforge.model_router import ModelRouter

        router = ModelRouter.from_config(model="claude-haiku-3-5")

        p1 = router.get_llm_for_chapter("03-architecture.md")
        p2 = router.get_llm_for_chapter("index.md")
        p3 = router.get_llm_for_chapter("05-data-models.md")

        assert p1 is p2 is p3 is single_prov
        assert not router.is_multi_model


class TestCLIOverridePrecedence:
    """CLI --model-heavy wins over repoforge.yaml models.heavy."""

    @patch("repoforge.model_router.build_llm")
    def test_cli_override_takes_precedence(self, mock_build):
        cli_heavy = _make_provider("cli-heavy-model")
        yaml_heavy = _make_provider("yaml-heavy-model")
        yaml_std = _make_provider("yaml-std")
        yaml_light = _make_provider("yaml-light")

        mock_build.side_effect = _build_llm_dispatch({
            "cli-heavy-model": cli_heavy,
            "yaml-heavy-model": yaml_heavy,
            "yaml-std": yaml_std,
            "yaml-light": yaml_light,
        })

        from repoforge.model_router import ModelRouter

        cfg = {
            "models": {
                "heavy": "yaml-heavy-model",
                "standard": "yaml-std",
                "light": "yaml-light",
            }
        }
        overrides = {"heavy": "cli-heavy-model", "standard": None, "light": None}
        router = ModelRouter.from_config(model="auto", config=cfg, cli_overrides=overrides)

        # Heavy: CLI override wins
        assert router.get_llm_for_chapter("03-architecture.md") is cli_heavy
        # Standard: config value preserved
        assert router.get_llm_for_chapter("05-data-models.md") is yaml_std

    @patch("repoforge.model_router.build_llm")
    def test_auto_no_config_auto_detects_all(self, mock_build):
        """--model auto without models config: all tiers auto-detect."""
        auto_prov = _make_provider("auto-detected")
        mock_build.side_effect = _build_llm_dispatch({None: auto_prov})

        from repoforge.model_router import ModelRouter

        router = ModelRouter.from_config(model="auto", config={})

        p1 = router.get_llm_for_chapter("03-architecture.md")
        p2 = router.get_llm_for_chapter("index.md")
        # All should resolve to the same auto-detected provider
        assert p1 is p2 is auto_prov
