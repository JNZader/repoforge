"""
model_router.py - Smart model routing per chapter tier.

Maps chapter filenames to LLM tiers (heavy/standard/light) so that
complex chapters get a powerful model while simple ones use a cheaper one.

Usage:
    router = ModelRouter(models_cfg={"heavy": "claude-sonnet-4", ...})
    llm = router.get_llm_for_chapter("03-architecture.md")  # heavy tier
    llm = router.get_llm_for_chapter("index.md")             # light tier
"""

import logging
import os
from typing import Optional

from .llm import LLMProvider, build_llm

logger = logging.getLogger(__name__)

_UNSET = object()  # sentinel for "key not present in merged config"

# ---------------------------------------------------------------------------
# Tier mapping: chapter filename -> tier name
# ---------------------------------------------------------------------------

TIER_MAP: dict[str, str] = {
    # heavy - complex analytical chapters
    "03-architecture.md": "heavy",
    "04-core-mechanisms.md": "heavy",
    # light - simple / templated chapters
    "index.md": "light",
    "02-quickstart.md": "light",
    "07-dev-guide.md": "light",
    # everything else -> "standard" (default)
}

# Tier fallback chain: if a tier's model fails init, try the next one
_FALLBACK_CHAIN = {
    "heavy": "standard",
    "standard": "light",
    "light": None,
}


class ModelRouter:
    """Route chapter generation to tier-specific LLM providers.

    Caches ``LLMProvider`` instances by model string so that chapters
    sharing a tier (and therefore a model) reuse the same provider.
    """

    def __init__(
        self,
        models_cfg: dict[str, str] | None = None,
        cli_overrides: dict[str, str | None] | None = None,
        fallback_model: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_base = api_base
        self._providers: dict[str, LLMProvider] = {}

        # Merge config: CLI overrides win over yaml config
        merged: dict[str, str | None] = {}
        if models_cfg:
            merged.update(models_cfg)
        if cli_overrides:
            for k, v in cli_overrides.items():
                if v is not None:
                    merged[k] = v

        # Resolve final model string per tier.
        # A sentinel value of _AUTO means "let build_llm auto-detect".
        self._tier_models: dict[str, str | None] = {}
        for tier in ("heavy", "standard", "light"):
            val = merged.get(tier, _UNSET)
            if val is not _UNSET and val is not None:
                self._tier_models[tier] = val
            elif fallback_model is not None:
                self._tier_models[tier] = fallback_model
            elif val is None and tier in merged:
                # Explicitly passed None → auto-detect
                self._tier_models[tier] = None
            # else: tier is not configured at all — skip

        # Build providers with fallback chain
        for tier in ("heavy", "standard", "light"):
            if tier in self._tier_models:
                self._ensure_provider(tier)

    def _ensure_provider(self, tier: str) -> None:
        """Build (or fallback) the provider for *tier*."""
        if tier not in self._tier_models:
            return

        model_str = self._tier_models[tier]
        # Use a cache key: None → "_auto_" sentinel to allow caching auto-detect
        cache_key = model_str if model_str is not None else "_auto_"

        # Already cached?
        if cache_key in self._providers:
            return

        try:
            provider = build_llm(
                model=model_str,
                api_key=self._api_key,
                api_base=self._api_base,
            )
            self._providers[cache_key] = provider
        except Exception as exc:
            fallback_tier = _FALLBACK_CHAIN.get(tier)
            if fallback_tier and fallback_tier in self._tier_models:
                logger.warning(
                    "build_llm failed for tier '%s' (model=%s): %s — "
                    "falling back to '%s' tier",
                    tier, model_str, exc, fallback_tier,
                )
                # Point this tier to the fallback tier's model
                self._tier_models[tier] = self._tier_models[fallback_tier]
                self._ensure_provider(tier)
            else:
                raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_tier(self, chapter_file: str) -> str:
        """Return the tier name for *chapter_file* (strips subdirs)."""
        basename = os.path.basename(chapter_file)
        return TIER_MAP.get(basename, "standard")

    def get_llm_for_chapter(self, chapter_file: str) -> LLMProvider:
        """Resolve *chapter_file* to its tier and return the cached provider."""
        tier = self.get_tier(chapter_file)
        if tier not in self._tier_models:
            raise ValueError(f"No model configured for tier '{tier}'")

        model_str = self._tier_models[tier]
        cache_key = model_str if model_str is not None else "_auto_"
        provider = self._providers[cache_key]
        logger.info("Model for %s: %s (tier: %s)", chapter_file, model_str, tier)
        return provider

    @property
    def is_multi_model(self) -> bool:
        """True when at least 2 distinct model strings are configured."""
        return len(set(self._tier_models.values())) >= 2

    @property
    def model(self) -> str:
        """Return a display-friendly model string (for logging)."""
        unique = sorted(set(str(v) for v in self._tier_models.values()))
        if len(unique) == 1:
            return unique[0]
        parts = [f"{t}={self._tier_models[t]}" for t in ("heavy", "standard", "light")
                 if t in self._tier_models]
        return "auto(" + ", ".join(parts) + ")"

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(
        cls,
        model: Optional[str] = None,
        config: Optional[dict] = None,
        cli_overrides: Optional[dict[str, str | None]] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ) -> "ModelRouter":
        """Build a ``ModelRouter`` from CLI args and ``repoforge.yaml``.

        If *model* is not ``"auto"``, wraps it in all three tiers (single-
        model mode, fully backwards compatible).  If ``"auto"``, reads
        ``models.heavy / standard / light`` from *config* and merges
        *cli_overrides* on top.
        """
        if model != "auto":
            # Single-model mode: same model for every tier
            effective = model  # may be None → build_llm auto-detects
            return cls(
                models_cfg={
                    "heavy": effective,
                    "standard": effective,
                    "light": effective,
                },
                api_key=api_key,
                api_base=api_base,
            )

        # Auto mode: read per-tier models from config
        models_section = (config or {}).get("models", {}) or {}
        models_cfg = {
            "heavy": models_section.get("heavy"),
            "standard": models_section.get("standard"),
            "light": models_section.get("light"),
        }

        return cls(
            models_cfg=models_cfg,
            cli_overrides=cli_overrides,
            fallback_model=None,  # auto-detect per tier if not set
            api_key=api_key,
            api_base=api_base,
        )
