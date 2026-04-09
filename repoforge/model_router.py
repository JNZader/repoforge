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
# Cost weights: model substring -> relative cost (first match wins)
# ---------------------------------------------------------------------------
# Order matters: more specific substrings MUST come before broader ones
# (e.g. "gpt-4o-mini" before "gpt-4o").

DEFAULT_COST_WEIGHT: int = 5

COST_WEIGHTS: list[tuple[str, int]] = [
    # Anthropic
    ("haiku", 1),
    ("sonnet", 5),
    ("opus", 25),
    # OpenAI — specific before broad
    ("gpt-4.1-nano", 1),
    ("gpt-4.1-mini", 1),
    ("gpt-4.1", 10),
    ("gpt-4o-mini", 1),
    ("gpt-4o", 10),
    ("o3-mini", 2),
    ("o3", 15),
    ("o4-mini", 2),
    # Google — match on "flash"/"pro" keywords within model string
    ("gemini-flash", 1),
    ("flash", 1),
    ("gemini-pro", 5),
    # Open-source / budget
    ("deepseek", 1),
    ("llama", 1),
    ("mistral", 2),
    ("mixtral", 3),
]

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

    def get_llm_for_chapter(
        self,
        chapter_file: str,
        *,
        model_override: str | None = None,
        tier_override: str | None = None,
    ) -> LLMProvider:
        """Resolve *chapter_file* to its tier and return the cached provider.

        When *model_override* is set, build (and cache) a provider for that
        specific model string, bypassing TIER_MAP entirely.

        When *tier_override* is set, use that tier instead of TIER_MAP lookup.

        Precedence: model_override > tier_override > TIER_MAP.
        """
        # --- explicit model override: highest precedence ---
        if model_override is not None:
            cache_key = model_override
            if cache_key not in self._providers:
                provider = build_llm(
                    model=model_override,
                    api_key=self._api_key,
                    api_base=self._api_base,
                )
                self._providers[cache_key] = provider
            logger.info(
                "Model for %s: %s (override)", chapter_file, model_override,
            )
            return self._providers[cache_key]

        # --- tier override: use specified tier instead of TIER_MAP ---
        tier = tier_override if tier_override is not None else self.get_tier(chapter_file)

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
    # Cost estimation
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_cost_weight(model_str: str | None) -> int:
        """Return the relative cost weight for *model_str*.

        Iterates :data:`COST_WEIGHTS` and returns the weight for the first
        substring match (case-insensitive).  Falls back to
        :data:`DEFAULT_COST_WEIGHT` when no entry matches.
        """
        if model_str is None:
            return DEFAULT_COST_WEIGHT
        lower = model_str.lower()
        for substring, weight in COST_WEIGHTS:
            if substring in lower:
                return weight
        return DEFAULT_COST_WEIGHT

    def get_cost_weight(self, chapter_file: str) -> int:
        """Return the relative cost weight for the model assigned to *chapter_file*."""
        tier = self.get_tier(chapter_file)
        model_str = self._tier_models.get(tier)
        return self._resolve_cost_weight(model_str)

    def estimate_total_cost(self, chapters: list[dict]) -> dict:
        """Estimate relative cost for a list of chapter dicts.

        Each chapter dict must have a ``"file"`` key.  Returns::

            {
                "breakdown": {
                    "heavy":    {"count": 2, "weight": 25, "subtotal": 50},
                    "standard": {"count": 3, "weight": 5,  "subtotal": 15},
                    ...
                },
                "total": 65,
                "display": "Estimated relative cost: 65 (2 heavy × 25 + 3 standard × 5)",
            }
        """
        buckets: dict[str, dict] = {}
        total = 0

        for ch in chapters:
            fname = ch["file"]
            tier = self.get_tier(fname)
            weight = self.get_cost_weight(fname)

            if tier not in buckets:
                buckets[tier] = {"count": 0, "weight": weight, "subtotal": 0}
            buckets[tier]["count"] += 1
            buckets[tier]["subtotal"] += weight
            total += weight

        # Build human-friendly display string
        parts = []
        for tier in ("heavy", "standard", "light"):
            if tier in buckets:
                b = buckets[tier]
                parts.append(f"{b['count']} {tier} \u00d7 {b['weight']}")

        display = f"Estimated relative cost: {total}"
        if parts:
            display += f" ({' + '.join(parts)})"

        return {"breakdown": buckets, "total": total, "display": display}

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
