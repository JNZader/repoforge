"""Unit tests for the Hybrid search index (BM25 + FAISS RRF fusion)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

np = pytest.importorskip("numpy", reason="numpy not installed")
faiss = pytest.importorskip("faiss", reason="faiss-cpu not installed")

from repoforge.search.bm25 import BM25Index
from repoforge.search.embedder import Embedder
from repoforge.search.hybrid import HybridSearchIndex, _rrf_score
from repoforge.search.index import SearchIndex


def _make_embedder_mock(dim: int = 8):
    """Create a mock Embedder returning deterministic vectors."""
    call_count = [0]

    def fake_embed(texts):
        vecs = []
        for _ in texts:
            call_count[0] += 1
            vec = np.random.RandomState(call_count[0]).randn(dim).tolist()
            vecs.append(vec)
        return vecs

    def fake_embed_single(text):
        return fake_embed([text])[0]

    mock = MagicMock(spec=Embedder)
    mock.embed.side_effect = fake_embed
    mock.embed_single.side_effect = fake_embed_single
    mock.model = "text-embedding-3-small"
    mock.batch_size = 100
    mock.dimension = 0
    mock.api_key = None
    mock.api_base = None
    return mock


SAMPLE_TEXTS = [
    "function authenticate in auth.py: params: token, secret",
    "class UserService in service.py",
    "function connect_db in database.py: params: host, port",
]
SAMPLE_IDS = ["auth.py::authenticate", "service.py::UserService", "database.py::connect_db"]
SAMPLE_TYPES = ["symbol", "symbol", "symbol"]


class TestRRFScore:
    def test_rrf_rank_1(self):
        assert _rrf_score(1, k=60) == pytest.approx(1 / 61)

    def test_rrf_rank_decreasing(self):
        assert _rrf_score(1) > _rrf_score(2) > _rrf_score(10)


class TestHybridSearchIndex:
    @pytest.fixture
    def hybrid_index(self):
        mock_embedder = _make_embedder_mock(dim=8)
        semantic = SearchIndex(embedder=mock_embedder)
        bm25 = BM25Index()

        idx = HybridSearchIndex(bm25=bm25, semantic=semantic)
        idx.add(texts=SAMPLE_TEXTS, ids=SAMPLE_IDS, types=SAMPLE_TYPES)
        return idx

    def test_add_populates_both(self, hybrid_index):
        assert hybrid_index.bm25.size == 3
        assert hybrid_index.semantic.size == 3

    def test_size(self, hybrid_index):
        assert hybrid_index.size == 3

    def test_search_hybrid(self, hybrid_index):
        results = hybrid_index.search("authenticate token", top_k=3)
        assert len(results) > 0
        # All results should have positive scores
        for r in results:
            assert r.score > 0

    def test_search_alpha_0_is_bm25_only(self, hybrid_index):
        """alpha=0 should weight BM25 fully."""
        results = hybrid_index.search("authenticate", top_k=3, alpha=0.0)
        bm25_results = hybrid_index.bm25.search("authenticate", top_k=3)

        # Same top result
        assert results[0].entity_id == bm25_results[0].entity_id

    def test_search_empty_index(self):
        idx = HybridSearchIndex()
        assert idx.search("anything") == []

    def test_search_bm25_only_fallback(self):
        """When semantic is None, should fall back to BM25."""
        bm25 = BM25Index()
        bm25.add(texts=SAMPLE_TEXTS, ids=SAMPLE_IDS, entity_types=SAMPLE_TYPES)
        idx = HybridSearchIndex(bm25=bm25, semantic=None)

        results = idx.search("authenticate", top_k=3)
        assert len(results) > 0
        assert results[0].entity_id == "auth.py::authenticate"

    def test_search_semantic_only_fallback(self):
        """When BM25 is empty, should fall back to semantic-only."""
        mock_embedder = _make_embedder_mock(dim=8)
        semantic = SearchIndex(embedder=mock_embedder)
        semantic.add(texts=SAMPLE_TEXTS, ids=SAMPLE_IDS, types=SAMPLE_TYPES)

        idx = HybridSearchIndex(bm25=BM25Index(), semantic=semantic)
        results = idx.search("authenticate", top_k=3)
        assert len(results) > 0


class TestHybridPersistence:
    def test_save_and_load(self, tmp_path):
        mock_embedder = _make_embedder_mock(dim=8)
        semantic = SearchIndex(embedder=mock_embedder)
        bm25 = BM25Index()

        idx = HybridSearchIndex(bm25=bm25, semantic=semantic)
        idx.add(texts=SAMPLE_TEXTS, ids=SAMPLE_IDS, types=SAMPLE_TYPES)
        idx.save(tmp_path)

        # Verify both files exist
        assert (tmp_path / "bm25_index.json").exists()
        assert (tmp_path / "index.faiss").exists()
        assert (tmp_path / "metadata.json").exists()

        # Load with a new mock embedder
        load_embedder = _make_embedder_mock(dim=8)
        loaded = HybridSearchIndex.load(tmp_path, embedder=load_embedder)
        assert loaded.size == 3

        results = loaded.search("database", top_k=2)
        assert len(results) > 0

    def test_load_bm25_only(self, tmp_path):
        """When FAISS index doesn't exist on disk, should load BM25 only."""
        bm25 = BM25Index()
        bm25.add(texts=SAMPLE_TEXTS, ids=SAMPLE_IDS, entity_types=SAMPLE_TYPES)
        bm25.save(tmp_path)

        # No FAISS files on disk — should load BM25 only
        loaded = HybridSearchIndex.load(tmp_path)
        assert loaded.size == 3
        assert loaded.semantic is None

        results = loaded.search("authenticate")
        assert len(results) > 0
