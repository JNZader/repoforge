"""Unit tests for the BM25 keyword search index."""

import json
from pathlib import Path

import pytest

from repoforge.search.bm25 import BM25Index, _tokenize


class TestTokenize:
    def test_lowercase_and_split(self):
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_strips_punctuation(self):
        tokens = _tokenize("user.name: get_user(id)")
        assert "user" in tokens
        assert "name" in tokens
        assert "get_user" in tokens or "get" in tokens

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_whitespace_only(self):
        assert _tokenize("   ") == []


class TestBM25Index:
    @pytest.fixture
    def sample_index(self):
        idx = BM25Index()
        idx.add(
            texts=[
                "function authenticate in auth.py: params: token, secret",
                "class UserService in service.py",
                "function connect_db in database.py: params: host, port",
            ],
            ids=["auth.py::authenticate", "service.py::UserService", "database.py::connect_db"],
            entity_types=["symbol", "symbol", "symbol"],
        )
        return idx

    def test_add_returns_count(self):
        idx = BM25Index()
        count = idx.add(
            texts=["hello world"],
            ids=["1"],
            entity_types=["symbol"],
        )
        assert count == 1

    def test_add_empty_returns_zero(self):
        idx = BM25Index()
        assert idx.add(texts=[], ids=[], entity_types=[]) == 0

    def test_add_mismatched_lengths(self):
        idx = BM25Index()
        with pytest.raises(ValueError, match="equal length"):
            idx.add(texts=["a", "b"], ids=["1"], entity_types=["symbol"])

    def test_size(self, sample_index):
        assert sample_index.size == 3

    def test_search_empty_index(self):
        idx = BM25Index()
        assert idx.search("anything") == []

    def test_search_empty_query(self, sample_index):
        assert sample_index.search("") == []

    def test_search_basic(self, sample_index):
        results = sample_index.search("authenticate token")
        assert len(results) > 0
        assert results[0].entity_id == "auth.py::authenticate"

    def test_search_top_k(self, sample_index):
        results = sample_index.search("function", top_k=1)
        assert len(results) == 1

    def test_search_returns_search_results(self, sample_index):
        results = sample_index.search("database")
        assert len(results) > 0
        r = results[0]
        assert r.entity_id == "database.py::connect_db"
        assert r.entity_type == "symbol"
        assert r.score > 0
        assert "database" in r.text.lower()

    def test_search_no_match(self, sample_index):
        results = sample_index.search("zzzzzzzzz")
        assert results == []


class TestBM25Persistence:
    def test_save_and_load(self, tmp_path):
        idx = BM25Index(k1=1.2, b=0.8)
        idx.add(
            texts=["function hello in main.py", "class Foo in bar.py"],
            ids=["main.py::hello", "bar.py::Foo"],
            entity_types=["symbol", "symbol"],
        )
        idx.save(tmp_path)

        loaded = BM25Index.load(tmp_path)
        assert loaded.size == 2
        assert loaded.k1 == 1.2
        assert loaded.b == 0.8

        # Search should work on loaded index
        results = loaded.search("hello")
        assert len(results) > 0
        assert results[0].entity_id == "main.py::hello"

    def test_save_empty_raises(self, tmp_path):
        idx = BM25Index()
        with pytest.raises(ValueError, match="empty"):
            idx.save(tmp_path)

    def test_load_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            BM25Index.load(tmp_path)

    def test_save_creates_directory(self, tmp_path):
        deep_path = tmp_path / "a" / "b" / "c"
        idx = BM25Index()
        idx.add(texts=["hello"], ids=["1"], entity_types=["symbol"])
        idx.save(deep_path)
        assert (deep_path / "bm25_index.json").exists()

    def test_serialized_format(self, tmp_path):
        """Verify the JSON structure is correct."""
        idx = BM25Index()
        idx.add(texts=["test doc"], ids=["id1"], entity_types=["symbol"])
        idx.save(tmp_path)

        data = json.loads((tmp_path / "bm25_index.json").read_text())
        assert "k1" in data
        assert "b" in data
        assert "ids" in data
        assert "texts" in data
        assert "df" in data
        assert data["n_docs"] == 1
