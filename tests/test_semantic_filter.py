"""Tests for repoforge.semantic_filter — SemanticFilter class."""

from __future__ import annotations

import json
import math
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repoforge.semantic_filter import (
    CACHE_FILENAME,
    SemanticCache,
    SemanticFilter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_embedder(model: str = "text-embedding-3-small") -> MagicMock:
    """Create a mock Embedder with configurable embed_single."""
    embedder = MagicMock()
    embedder.model = model
    return embedder


def _make_chapter(fname: str, title: str = "Test") -> dict:
    return {"file": fname, "title": title}


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    """Unit tests for SemanticFilter._cosine_similarity."""

    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        result = SemanticFilter._cosine_similarity(v, v)
        assert result == pytest.approx(1.0, abs=1e-9)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        result = SemanticFilter._cosine_similarity(a, b)
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        result = SemanticFilter._cosine_similarity(a, b)
        assert result == pytest.approx(-1.0, abs=1e-9)

    def test_similar_vectors(self):
        a = [1.0, 2.0, 3.0]
        b = [1.1, 2.1, 3.1]
        result = SemanticFilter._cosine_similarity(a, b)
        assert result > 0.99  # very similar

    def test_zero_vector_returns_zero(self):
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert SemanticFilter._cosine_similarity(a, b) == 0.0
        assert SemanticFilter._cosine_similarity(b, a) == 0.0

    def test_different_length_returns_zero(self):
        a = [1.0, 2.0]
        b = [1.0, 2.0, 3.0]
        assert SemanticFilter._cosine_similarity(a, b) == 0.0


# ---------------------------------------------------------------------------
# aggregate_source
# ---------------------------------------------------------------------------


class TestAggregateSource:
    """Unit tests for SemanticFilter._aggregate_source."""

    def test_concatenates_in_sorted_order(self, tmp_path: Path):
        (tmp_path / "b.py").write_text("BBB", encoding="utf-8")
        (tmp_path / "a.py").write_text("AAA", encoding="utf-8")
        result = SemanticFilter._aggregate_source(["b.py", "a.py"], tmp_path)
        # sorted order → a.py before b.py
        assert result == "AAA\nBBB"

    def test_missing_file_skipped(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("AAA", encoding="utf-8")
        result = SemanticFilter._aggregate_source(
            ["a.py", "missing.py"], tmp_path,
        )
        assert result == "AAA"

    def test_empty_paths_returns_empty(self, tmp_path: Path):
        result = SemanticFilter._aggregate_source([], tmp_path)
        assert result == ""


# ---------------------------------------------------------------------------
# Cache load / save
# ---------------------------------------------------------------------------


class TestCacheIO:
    """Unit tests for cache load/save and model invalidation."""

    def test_round_trip(self, tmp_path: Path):
        embedder = _make_embedder("model-a")
        sf = SemanticFilter(embedder=embedder, cache_dir=tmp_path)

        cache = SemanticCache(
            model="model-a",
            generated_at="2026-01-01T00:00:00Z",
            chapters={"ch.md": [0.1, 0.2, 0.3]},
        )
        sf._save_cache(cache)

        # Reset internal cache to force reload
        sf._cache = None
        loaded = sf._load_cache()
        assert loaded is not None
        assert loaded.model == "model-a"
        assert loaded.chapters["ch.md"] == [0.1, 0.2, 0.3]

    def test_model_change_invalidates(self, tmp_path: Path):
        # Write cache with model-a
        cache_path = tmp_path / CACHE_FILENAME
        cache_path.write_text(
            json.dumps({
                "model": "model-a",
                "generated_at": "2026-01-01T00:00:00Z",
                "chapters": {"ch.md": [0.1]},
            }),
            encoding="utf-8",
        )

        # Load with model-b → should return None
        embedder = _make_embedder("model-b")
        sf = SemanticFilter(embedder=embedder, cache_dir=tmp_path)
        assert sf._load_cache() is None

    def test_missing_cache_returns_none(self, tmp_path: Path):
        sf = SemanticFilter(
            embedder=_make_embedder(), cache_dir=tmp_path,
        )
        assert sf._load_cache() is None

    def test_corrupt_cache_returns_none(self, tmp_path: Path):
        (tmp_path / CACHE_FILENAME).write_text("not json!", encoding="utf-8")
        sf = SemanticFilter(
            embedder=_make_embedder(), cache_dir=tmp_path,
        )
        assert sf._load_cache() is None

    def test_no_cache_dir_returns_none(self):
        sf = SemanticFilter(embedder=_make_embedder(), cache_dir=None)
        assert sf._load_cache() is None


# ---------------------------------------------------------------------------
# filter_stale
# ---------------------------------------------------------------------------


class TestFilterStale:
    """Unit tests for SemanticFilter.filter_stale."""

    def test_above_threshold_skipped(self, tmp_path: Path):
        """Chapter with sim >= threshold is removed from stale list."""
        (tmp_path / "src.py").write_text("hello world", encoding="utf-8")

        # Pre-populate cache
        cached_vec = [1.0, 0.0, 0.0]
        cache_path = tmp_path / CACHE_FILENAME
        cache_path.write_text(
            json.dumps({
                "model": "text-embedding-3-small",
                "generated_at": "2026-01-01T00:00:00Z",
                "chapters": {"ch.md": cached_vec},
            }),
            encoding="utf-8",
        )

        embedder = _make_embedder()
        # Return a vector very similar to cached (same direction)
        embedder.embed_single.return_value = [1.0, 0.001, 0.0]

        sf = SemanticFilter(
            threshold=0.95, embedder=embedder, cache_dir=tmp_path,
        )
        stale = [_make_chapter("ch.md")]
        deps = {"ch.md": ["src.py"]}

        result = sf.filter_stale(stale, deps, tmp_path)
        assert result == []  # skipped — similarity is ~1.0

    def test_below_threshold_kept(self, tmp_path: Path):
        """Chapter with sim < threshold remains in stale list."""
        (tmp_path / "src.py").write_text("hello world", encoding="utf-8")

        cached_vec = [1.0, 0.0, 0.0]
        cache_path = tmp_path / CACHE_FILENAME
        cache_path.write_text(
            json.dumps({
                "model": "text-embedding-3-small",
                "generated_at": "2026-01-01T00:00:00Z",
                "chapters": {"ch.md": cached_vec},
            }),
            encoding="utf-8",
        )

        embedder = _make_embedder()
        # Return an orthogonal vector — similarity ≈ 0
        embedder.embed_single.return_value = [0.0, 1.0, 0.0]

        sf = SemanticFilter(
            threshold=0.95, embedder=embedder, cache_dir=tmp_path,
        )
        stale = [_make_chapter("ch.md")]
        deps = {"ch.md": ["src.py"]}

        result = sf.filter_stale(stale, deps, tmp_path)
        assert len(result) == 1
        assert result[0]["file"] == "ch.md"

    def test_no_cache_returns_all_stale(self, tmp_path: Path):
        """No cache file → all chapters remain stale."""
        (tmp_path / "src.py").write_text("x", encoding="utf-8")

        embedder = _make_embedder()
        sf = SemanticFilter(
            threshold=0.95, embedder=embedder, cache_dir=tmp_path,
        )

        stale = [_make_chapter("a.md"), _make_chapter("b.md")]
        result = sf.filter_stale(stale, {}, tmp_path)
        assert len(result) == 2

    def test_new_chapter_without_cached_vec_kept(self, tmp_path: Path):
        """Chapter not in cache → stays stale."""
        (tmp_path / "src.py").write_text("x", encoding="utf-8")

        cache_path = tmp_path / CACHE_FILENAME
        cache_path.write_text(
            json.dumps({
                "model": "text-embedding-3-small",
                "generated_at": "2026-01-01T00:00:00Z",
                "chapters": {},  # empty cache
            }),
            encoding="utf-8",
        )

        embedder = _make_embedder()
        sf = SemanticFilter(
            threshold=0.95, embedder=embedder, cache_dir=tmp_path,
        )

        stale = [_make_chapter("new.md")]
        result = sf.filter_stale(stale, {"new.md": ["src.py"]}, tmp_path)
        assert len(result) == 1

    def test_graceful_fallback_on_embedder_error(self, tmp_path: Path):
        """If embedder raises, returns original stale list (REQ-6)."""
        (tmp_path / "src.py").write_text("x", encoding="utf-8")

        cache_path = tmp_path / CACHE_FILENAME
        cache_path.write_text(
            json.dumps({
                "model": "text-embedding-3-small",
                "generated_at": "2026-01-01T00:00:00Z",
                "chapters": {"ch.md": [1.0, 0.0]},
            }),
            encoding="utf-8",
        )

        embedder = _make_embedder()
        embedder.embed_single.side_effect = RuntimeError("API down")

        sf = SemanticFilter(
            threshold=0.95, embedder=embedder, cache_dir=tmp_path,
        )

        stale = [_make_chapter("ch.md")]
        deps = {"ch.md": ["src.py"]}
        result = sf.filter_stale(stale, deps, tmp_path)
        # Graceful fallback: returns original list
        assert len(result) == 1
        assert result[0]["file"] == "ch.md"


# ---------------------------------------------------------------------------
# update_cache
# ---------------------------------------------------------------------------


class TestUpdateCache:
    """Unit tests for SemanticFilter.update_cache."""

    def test_creates_cache_file(self, tmp_path: Path):
        (tmp_path / "src.py").write_text("code", encoding="utf-8")

        embedder = _make_embedder()
        embedder.embed_single.return_value = [0.5, 0.5]

        sf = SemanticFilter(
            embedder=embedder, cache_dir=tmp_path,
        )

        gen_path = str(tmp_path / "ch.md")
        sf.update_cache([gen_path], {"ch.md": ["src.py"]}, tmp_path)

        cache_file = tmp_path / CACHE_FILENAME
        assert cache_file.exists()
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        assert data["model"] == "text-embedding-3-small"
        assert data["chapters"]["ch.md"] == [0.5, 0.5]

    def test_updates_existing_cache(self, tmp_path: Path):
        (tmp_path / "src.py").write_text("code", encoding="utf-8")

        # Pre-populate cache with old chapter
        cache_path = tmp_path / CACHE_FILENAME
        cache_path.write_text(
            json.dumps({
                "model": "text-embedding-3-small",
                "generated_at": "2026-01-01T00:00:00Z",
                "chapters": {"old.md": [1.0, 0.0]},
            }),
            encoding="utf-8",
        )

        embedder = _make_embedder()
        embedder.embed_single.return_value = [0.3, 0.7]

        sf = SemanticFilter(embedder=embedder, cache_dir=tmp_path)

        gen_path = str(tmp_path / "new.md")
        sf.update_cache([gen_path], {"new.md": ["src.py"]}, tmp_path)

        data = json.loads(cache_path.read_text(encoding="utf-8"))
        # Old chapter preserved, new chapter added
        assert "old.md" in data["chapters"]
        assert data["chapters"]["new.md"] == [0.3, 0.7]


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------


class TestIntegration:
    """End-to-end test with mocked embedder returning controlled vectors."""

    def test_cosmetic_change_skipped_real_change_regenerated(
        self, tmp_path: Path,
    ):
        """Cosmetic change (high sim) is skipped, real change (low sim)
        is kept for regeneration."""
        # Create source files
        (tmp_path / "cosmetic_src.py").write_text("# cosmetic", encoding="utf-8")
        (tmp_path / "real_src.py").write_text("# real change", encoding="utf-8")

        # Cached vectors (one per chapter)
        cached = {
            "cosmetic.md": [1.0, 0.0, 0.0],
            "real.md": [1.0, 0.0, 0.0],
        }
        cache_path = tmp_path / CACHE_FILENAME
        cache_path.write_text(
            json.dumps({
                "model": "text-embedding-3-small",
                "generated_at": "2026-01-01T00:00:00Z",
                "chapters": cached,
            }),
            encoding="utf-8",
        )

        # Mock embedder: cosmetic returns near-identical, real returns different
        embedder = _make_embedder()

        def _embed_single(text: str) -> list[float]:
            if "cosmetic" in text:
                return [0.999, 0.01, 0.01]  # sim ≈ 0.998
            return [0.3, 0.8, 0.5]  # sim ≈ 0.30

        embedder.embed_single.side_effect = _embed_single

        sf = SemanticFilter(
            threshold=0.95, embedder=embedder, cache_dir=tmp_path,
        )

        stale = [
            _make_chapter("cosmetic.md"),
            _make_chapter("real.md"),
        ]
        deps = {
            "cosmetic.md": ["cosmetic_src.py"],
            "real.md": ["real_src.py"],
        }

        result = sf.filter_stale(stale, deps, tmp_path)

        # Only real.md should remain (cosmetic.md skipped)
        assert len(result) == 1
        assert result[0]["file"] == "real.md"

        # Now update cache for the "generated" chapter
        gen_path = str(tmp_path / "real.md")
        sf.update_cache([gen_path], deps, tmp_path)

        # Verify cache was updated
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert "real.md" in data["chapters"]
        assert data["chapters"]["real.md"] == [0.3, 0.8, 0.5]
        # Cosmetic chapter still in cache from before
        assert "cosmetic.md" in data["chapters"]
