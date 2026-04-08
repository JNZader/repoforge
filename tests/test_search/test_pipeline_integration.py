"""Integration test for the full search pipeline: prepare → embed → index → query."""

from unittest.mock import MagicMock

import pytest

np = pytest.importorskip("numpy", reason="numpy not installed")
faiss = pytest.importorskip("faiss", reason="faiss-cpu not installed")

from repoforge.graph import Node
from repoforge.search.embedder import Embedder
from repoforge.search.index import SearchIndex
from repoforge.search.prepare import prepare_all
from repoforge.search.types import SearchResult
from repoforge.symbols.extractor import Symbol


def _make_embedder_mock(dim: int = 8):
    """Create a mock Embedder that returns deterministic vectors."""
    embedder = MagicMock(spec=Embedder)
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

    embedder.embed.side_effect = fake_embed
    embedder.embed_single.side_effect = fake_embed_single
    return embedder


class TestFullPipeline:
    """End-to-end test: symbols + nodes → prepare → embed → index → query."""

    def _make_symbols(self):
        return [
            Symbol(
                name="authenticate",
                kind="function",
                file="src/auth.py",
                line=10,
                end_line=25,
                params=["token", "secret"],
            ),
            Symbol(
                name="UserService",
                kind="class",
                file="src/service.py",
                line=1,
                end_line=50,
                params=[],
            ),
            Symbol(
                name="connect_db",
                kind="function",
                file="src/database.py",
                line=5,
                end_line=15,
                params=["host", "port"],
            ),
        ]

    def _make_nodes(self):
        return [
            Node(
                id="src/auth.py",
                name="auth",
                node_type="module",
                layer="backend",
                file_path="src/auth.py",
                exports=["authenticate"],
            ),
            Node(
                id="src/service.py",
                name="service",
                node_type="module",
                layer="backend",
                file_path="src/service.py",
                exports=["UserService"],
            ),
        ]

    def test_full_pipeline_build_and_query(self):
        symbols = self._make_symbols()
        nodes = self._make_nodes()

        # Step 1: prepare entities
        entities = prepare_all(symbols=symbols, nodes=nodes)
        assert len(entities) == 5  # 3 symbols + 2 nodes

        ids = [e[0] for e in entities]
        types = [e[1] for e in entities]
        texts = [e[2] for e in entities]

        # Verify entity types
        assert types.count("symbol") == 3
        assert types.count("node") == 2

        # Step 2: embed and index
        embedder = _make_embedder_mock(dim=8)
        search_index = SearchIndex(embedder=embedder)
        added = search_index.add(texts=texts, ids=ids, types=types)
        assert added == 5
        assert search_index.size == 5

        # Step 3: query
        results = search_index.search("authentication logic", top_k=3)
        assert len(results) > 0
        assert len(results) <= 3
        assert all(isinstance(r, SearchResult) for r in results)

        # Verify result fields
        for r in results:
            assert r.entity_id in ids
            assert r.entity_type in ("symbol", "node")
            assert r.text in texts
            assert isinstance(r.score, float)

    def test_pipeline_save_load_and_query(self, tmp_path):
        symbols = self._make_symbols()
        nodes = self._make_nodes()

        entities = prepare_all(symbols=symbols, nodes=nodes)
        ids = [e[0] for e in entities]
        types = [e[1] for e in entities]
        texts = [e[2] for e in entities]

        embedder = _make_embedder_mock(dim=8)
        search_index = SearchIndex(embedder=embedder)
        search_index.add(texts=texts, ids=ids, types=types)

        # Save
        save_dir = tmp_path / "pipeline_index"
        search_index.save(save_dir)

        # Load with a fresh embedder mock
        fresh_embedder = _make_embedder_mock(dim=8)
        loaded = SearchIndex.load(save_dir, embedder=fresh_embedder)
        assert loaded.size == 5
        assert loaded.dimension == 8

        # Query the loaded index
        results = loaded.search("database connection", top_k=5)
        assert len(results) > 0
        assert all(isinstance(r, SearchResult) for r in results)

    def test_pipeline_empty_inputs(self):
        """prepare_all with no entities returns empty list."""
        entities = prepare_all()
        assert entities == []

    def test_pipeline_symbols_only(self):
        """Pipeline works with symbols only (no modules/nodes)."""
        symbols = self._make_symbols()
        entities = prepare_all(symbols=symbols)
        assert len(entities) == 3
        assert all(e[1] == "symbol" for e in entities)

        embedder = _make_embedder_mock(dim=8)
        search_index = SearchIndex(embedder=embedder)
        search_index.add(
            texts=[e[2] for e in entities],
            ids=[e[0] for e in entities],
            types=[e[1] for e in entities],
        )
        results = search_index.search("connect", top_k=2)
        assert len(results) > 0
