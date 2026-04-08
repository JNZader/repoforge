"""
semantic_filter.py - Semantic deduplication for incremental doc generation.

Embeds concatenated source deps per chapter, compares against cached
embeddings via cosine similarity, and removes chapters whose meaning
hasn't changed from the stale list.  Pure-Python cosine similarity
(no numpy required).

Cache format (.semantic_cache.json):
{
  "model": "text-embedding-3-small",
  "generated_at": "2026-04-08T20:00:00Z",
  "chapters": {
    "01-overview.md": [0.012, -0.034, ...]
  }
}
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .search.embedder import Embedder

logger = logging.getLogger(__name__)

CACHE_FILENAME = ".semantic_cache.json"


@dataclass
class SemanticCache:
    """In-memory representation of the semantic cache."""

    model: str = ""
    generated_at: str = ""
    chapters: dict[str, list[float]] = field(default_factory=dict)


class SemanticFilter:
    """Filter stale chapters by comparing source-embedding similarity.

    After file-level staleness detection marks chapters as stale,
    SemanticFilter provides a second pass: if the *meaning* of a
    chapter's source files hasn't changed (cosine similarity above
    threshold), the chapter is demoted from stale back to skipped.

    Args:
        threshold: Cosine similarity above which a chapter is skipped.
        embedder:  Embedder instance (default: create with default model).
        cache_dir: Directory for ``.semantic_cache.json`` (default: output dir).
    """

    def __init__(
        self,
        threshold: float = 0.95,
        embedder: Embedder | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.threshold = threshold
        self.embedder = embedder or Embedder()
        self.cache_dir = cache_dir
        self._cache: SemanticCache | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def filter_stale(
        self,
        stale_chapters: list[dict],
        chapter_deps: dict[str, list[str]],
        root: Path,
    ) -> list[dict]:
        """Remove chapters whose source meaning hasn't changed.

        For each stale chapter:
        1. Aggregate source file contents.
        2. Embed the concatenated text.
        3. Compare with cached embedding via cosine similarity.
        4. If sim >= threshold, skip (not truly stale).

        On any embedding error, returns the original stale list unchanged
        (graceful fallback).
        """
        try:
            return self._filter_stale_inner(stale_chapters, chapter_deps, root)
        except Exception as exc:
            logger.warning(
                "Semantic filter failed — falling back to file-level staleness: %s",
                exc,
            )
            return stale_chapters

    def update_cache(
        self,
        generated_chapters: list[str],
        chapter_deps: dict[str, list[str]],
        root: Path,
    ) -> None:
        """Re-embed and persist cache for chapters that were regenerated."""
        try:
            self._update_cache_inner(generated_chapters, chapter_deps, root)
        except Exception as exc:
            logger.warning("Failed to update semantic cache: %s", exc)

    # ------------------------------------------------------------------
    # Internal implementation
    # ------------------------------------------------------------------

    def _filter_stale_inner(
        self,
        stale_chapters: list[dict],
        chapter_deps: dict[str, list[str]],
        root: Path,
    ) -> list[dict]:
        cache = self._load_cache()

        # No cache → everything is stale
        if cache is None:
            return stale_chapters

        filtered: list[dict] = []
        for chapter in stale_chapters:
            fname = chapter["file"]
            cached_vec = cache.chapters.get(fname)

            if cached_vec is None:
                # New chapter, no cached embedding → keep as stale
                filtered.append(chapter)
                continue

            source_text = self._aggregate_source(
                chapter_deps.get(fname, []), root,
            )
            if not source_text:
                # Can't read sources → keep as stale
                filtered.append(chapter)
                continue

            new_vec = self.embedder.embed_single(source_text)
            sim = self._cosine_similarity(new_vec, cached_vec)

            if sim < self.threshold:
                # Meaning changed enough → regenerate
                filtered.append(chapter)
            else:
                logger.info(
                    "Semantic skip: %s (similarity=%.4f >= %.4f)",
                    fname, sim, self.threshold,
                )

        return filtered

    def _update_cache_inner(
        self,
        generated_chapters: list[str],
        chapter_deps: dict[str, list[str]],
        root: Path,
    ) -> None:
        # Start from existing cache or create new
        cache = self._load_cache() or SemanticCache(
            model=self.embedder.model,
            generated_at=_now_iso(),
        )

        for gen_path in generated_chapters:
            fname = Path(gen_path).name
            source_text = self._aggregate_source(
                chapter_deps.get(fname, []), root,
            )
            if not source_text:
                continue
            vec = self.embedder.embed_single(source_text)
            cache.chapters[fname] = vec

        cache.generated_at = _now_iso()
        self._save_cache(cache)

    # ------------------------------------------------------------------
    # Cosine similarity (pure Python, no numpy)
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Cosine similarity between two vectors.

        Returns a value in [-1, 1]. Returns 0.0 if either vector has
        zero magnitude (avoids division by zero).
        """
        if len(a) != len(b):
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        return dot / (norm_a * norm_b)

    # ------------------------------------------------------------------
    # Source aggregation
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate_source(file_paths: list[str], root: Path) -> str:
        """Concatenate source file contents in sorted path order."""
        parts: list[str] = []
        for path in sorted(file_paths):
            full = root / path
            try:
                parts.append(full.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                logger.debug("Cannot read source file: %s", full)
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Cache I/O
    # ------------------------------------------------------------------

    def _load_cache(self) -> SemanticCache | None:
        """Load cached embeddings from disk. Returns None if missing/corrupt."""
        if self._cache is not None:
            return self._cache

        if self.cache_dir is None:
            return None

        path = self.cache_dir / CACHE_FILENAME
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Corrupt semantic cache: %s", exc)
            return None

        cached_model = data.get("model", "")
        if cached_model != self.embedder.model:
            logger.info(
                "Embedding model changed (%s -> %s) — invalidating semantic cache",
                cached_model, self.embedder.model,
            )
            return None

        cache = SemanticCache(
            model=cached_model,
            generated_at=data.get("generated_at", ""),
            chapters=data.get("chapters", {}),
        )
        self._cache = cache
        return cache

    def _save_cache(self, cache: SemanticCache) -> None:
        """Persist cache to disk."""
        if self.cache_dir is None:
            return

        path = self.cache_dir / CACHE_FILENAME
        data = {
            "model": cache.model,
            "generated_at": cache.generated_at,
            "chapters": cache.chapters,
        }
        try:
            path.write_text(
                json.dumps(data, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Failed to write semantic cache: %s", exc)

        self._cache = cache


def _now_iso() -> str:
    """Current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()
