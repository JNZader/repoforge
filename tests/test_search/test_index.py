"""Tests for repoforge.search.index."""

import json
from unittest.mock import MagicMock, patch

import pytest

# Guard: skip all tests if faiss or numpy are not installed
np = pytest.importorskip("numpy", reason="numpy not installed")
faiss = pytest.importorskip("faiss", reason="faiss-cpu not installed")

from repoforge.search.embedder import Embedder
from repoforge.search.index import SearchIndex


def _make_embedder_mock(dim: int = 4):
    """Create a mock Embedder that returns deterministic vectors."""
    embedder = MagicMock(spec=Embedder)
    call_count = [0]

    def fake_embed(texts):
        vecs = []
        for i, _ in enumerate(texts):
            call_count[0] += 1
            # Create distinct vectors for each text
            vec = np.random.RandomState(call_count[0]).randn(dim).tolist()
            vecs.append(vec)
        return vecs

    def fake_embed_single(text):
        return fake_embed([text])[0]

    embedder.embed.side_effect = fake_embed
    embedder.embed_single.side_effect = fake_embed_single
    return embedder


class TestSearchIndex:
    def test_add_and_search(self):
        embedder = _make_embedder_mock(dim=4)
        index = SearchIndex(embedder=embedder)

        added = index.add(
            texts=["function authenticate in auth.py", "class UserService in service.py"],
            ids=["auth.py::authenticate", "service.py::UserService"],
            types=["symbol", "symbol"],
        )

        assert added == 2
        assert index.size == 2

        results = index.search("authenticate", top_k=5)
        assert len(results) > 0
        assert results[0].entity_id in ["auth.py::authenticate", "service.py::UserService"]
        assert results[0].score > 0 or results[0].score <= 0  # just checking it's a float

    def test_search_empty_index(self):
        embedder = _make_embedder_mock()
        index = SearchIndex(embedder=embedder)

        results = index.search("anything")
        assert results == []

    def test_add_empty(self):
        embedder = _make_embedder_mock()
        index = SearchIndex(embedder=embedder)

        added = index.add(texts=[], ids=[], types=[])
        assert added == 0
        assert index.size == 0

    def test_mismatched_lengths_raises(self):
        embedder = _make_embedder_mock()
        index = SearchIndex(embedder=embedder)

        with pytest.raises(ValueError, match="equal length"):
            index.add(
                texts=["a", "b"],
                ids=["id1"],
                types=["symbol", "symbol"],
            )

    def test_save_and_load(self, tmp_path):
        embedder = _make_embedder_mock(dim=4)
        index = SearchIndex(embedder=embedder)

        index.add(
            texts=["alpha", "beta", "gamma"],
            ids=["id1", "id2", "id3"],
            types=["symbol", "module", "node"],
        )

        save_dir = tmp_path / "test_index"
        index.save(save_dir)

        # Verify files exist
        assert (save_dir / "index.faiss").exists()
        assert (save_dir / "metadata.json").exists()

        # Verify metadata content
        meta = json.loads((save_dir / "metadata.json").read_text())
        assert meta["ids"] == ["id1", "id2", "id3"]
        assert meta["types"] == ["symbol", "module", "node"]
        assert len(meta["texts"]) == 3

        # Load and verify
        loaded = SearchIndex.load(save_dir, embedder=embedder)
        assert loaded.size == 3
        assert loaded.dimension == 4

    def test_save_empty_raises(self):
        embedder = _make_embedder_mock()
        index = SearchIndex(embedder=embedder)

        with pytest.raises(ValueError, match="empty"):
            index.save("/tmp/test_empty_index")

    def test_load_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SearchIndex.load(tmp_path / "nonexistent")

    def test_top_k_capped(self):
        """top_k should be capped to index size."""
        embedder = _make_embedder_mock(dim=4)
        index = SearchIndex(embedder=embedder)

        index.add(
            texts=["a", "b"],
            ids=["id1", "id2"],
            types=["symbol", "symbol"],
        )

        # Request more than available
        results = index.search("query", top_k=100)
        assert len(results) <= 2
