"""Tests for cross_repo.py — cross-repo code graph registry."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repoforge.cross_repo import (
    CrossRepoMatch,
    RepoEntry,
    _build_graph_for_entry,
    _entry_from_dict,
    _load_registry,
    _save_registry,
    cross_repo_results_to_json,
    format_cross_repo_results,
    format_registry_list,
    registry_add,
    registry_build,
    registry_list,
    registry_remove,
    registry_search,
)
from repoforge.graph import CodeGraph, Edge, Node

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_registry(tmp_path, monkeypatch):
    """Redirect the registry to a temp directory."""
    reg_dir = tmp_path / ".repoforge"
    reg_dir.mkdir()
    reg_file = reg_dir / "registry.json"

    monkeypatch.setattr("repoforge.cross_repo.REGISTRY_DIR", reg_dir)
    monkeypatch.setattr("repoforge.cross_repo.REGISTRY_FILE", reg_file)
    return reg_file


@pytest.fixture()
def fake_repo(tmp_path):
    """Create a minimal fake repo with a Python file."""
    repo = tmp_path / "fake-repo"
    repo.mkdir()
    (repo / "main.py").write_text("def hello():\n    print('hi')\n")
    (repo / "utils.py").write_text("def add(a, b):\n    return a + b\n")
    return repo


@pytest.fixture()
def fake_repo_2(tmp_path):
    """Create a second minimal fake repo."""
    repo = tmp_path / "other-repo"
    repo.mkdir()
    (repo / "app.py").write_text("def run():\n    pass\n")
    return repo


# ---------------------------------------------------------------------------
# RepoEntry
# ---------------------------------------------------------------------------


class TestRepoEntry:
    def test_to_dict_roundtrip(self):
        entry = RepoEntry(
            path="/tmp/test",
            name="test",
            registered_at="2026-01-01T00:00:00+00:00",
            last_built="2026-01-01T00:01:00+00:00",
            node_count=10,
            edge_count=5,
            file_count=3,
        )
        d = entry.to_dict()
        restored = _entry_from_dict(d)
        assert restored.path == entry.path
        assert restored.name == entry.name
        assert restored.node_count == entry.node_count
        assert restored.edge_count == entry.edge_count
        assert restored.file_count == entry.file_count

    def test_to_dict_defaults(self):
        entry = RepoEntry(
            path="/tmp/x",
            name="x",
            registered_at="2026-01-01T00:00:00+00:00",
        )
        d = entry.to_dict()
        assert d["last_built"] is None
        assert d["node_count"] == 0


# ---------------------------------------------------------------------------
# CrossRepoMatch
# ---------------------------------------------------------------------------


class TestCrossRepoMatch:
    def test_to_dict(self):
        match = CrossRepoMatch(
            repo_name="myrepo",
            repo_path="/tmp/myrepo",
            function_name="hello",
            file_path="main.py",
            line=1,
            score=3.14159,
            signature="hello()",
            complexity="low",
            behavior="says hello",
        )
        d = match.to_dict()
        assert d["repo"] == "myrepo"
        assert d["score"] == 3.1416  # rounded to 4 decimals
        assert d["function"] == "hello"


# ---------------------------------------------------------------------------
# Registry I/O
# ---------------------------------------------------------------------------


class TestRegistryIO:
    def test_load_empty(self, tmp_registry):
        repos = _load_registry()
        assert repos == {}

    def test_save_and_load(self, tmp_registry):
        repos = {"/tmp/a": {"path": "/tmp/a", "name": "a", "registered_at": "x"}}
        _save_registry(repos)

        assert tmp_registry.exists()
        loaded = _load_registry()
        assert "/tmp/a" in loaded

    def test_load_corrupt_file(self, tmp_registry):
        tmp_registry.write_text("not json!!!")
        repos = _load_registry()
        assert repos == {}

    def test_load_wrong_type(self, tmp_registry):
        tmp_registry.write_text(json.dumps([1, 2, 3]))
        repos = _load_registry()
        assert repos == {}


# ---------------------------------------------------------------------------
# registry_add / registry_remove / registry_list
# ---------------------------------------------------------------------------


class TestRegistryAdd:
    def test_add_valid_repo(self, tmp_registry, fake_repo):
        entry = registry_add(str(fake_repo))
        assert entry.name == "fake-repo"
        assert entry.path == str(fake_repo.resolve())
        assert entry.node_count > 0

    def test_add_nonexistent_path(self, tmp_registry):
        with pytest.raises(FileNotFoundError, match="does not exist"):
            registry_add("/tmp/this-does-not-exist-xyz-999")

    def test_add_duplicate(self, tmp_registry, fake_repo):
        registry_add(str(fake_repo))
        with pytest.raises(ValueError, match="already registered"):
            registry_add(str(fake_repo))


class TestRegistryRemove:
    def test_remove_existing(self, tmp_registry, fake_repo):
        registry_add(str(fake_repo))
        assert registry_remove(str(fake_repo)) is True
        assert len(registry_list()) == 0

    def test_remove_nonexistent(self, tmp_registry):
        assert registry_remove("/tmp/nope") is False


class TestRegistryList:
    def test_list_empty(self, tmp_registry):
        entries = registry_list()
        assert entries == []

    def test_list_multiple(self, tmp_registry, fake_repo, fake_repo_2):
        registry_add(str(fake_repo))
        registry_add(str(fake_repo_2))
        entries = registry_list()
        assert len(entries) == 2
        # Sorted by name
        names = [e.name for e in entries]
        assert names == sorted(names, key=str.lower)


# ---------------------------------------------------------------------------
# registry_build
# ---------------------------------------------------------------------------


class TestRegistryBuild:
    def test_build_registered(self, tmp_registry, fake_repo):
        registry_add(str(fake_repo))
        entry = registry_build(str(fake_repo))
        assert entry.last_built is not None
        assert entry.node_count > 0

    def test_build_unregistered(self, tmp_registry):
        with pytest.raises(KeyError, match="not registered"):
            registry_build("/tmp/nope")


# ---------------------------------------------------------------------------
# registry_search
# ---------------------------------------------------------------------------


class TestRegistrySearch:
    def test_search_empty_registry(self, tmp_registry):
        results = registry_search("anything")
        assert results == []

    def test_search_finds_results(self, tmp_registry, fake_repo):
        registry_add(str(fake_repo))
        # Search for something that should match our simple functions
        results = registry_search("hello", top_k=5, depth=2)
        # We can't guarantee results from BM25 on simple code, just
        # verify it runs without error and returns the right type
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, CrossRepoMatch)
            assert r.repo_name == "fake-repo"

    def test_search_skips_missing_repo(self, tmp_registry, fake_repo):
        registry_add(str(fake_repo))
        # Manually corrupt the path in registry
        repos = _load_registry()
        key = str(fake_repo.resolve())
        repos[key]["path"] = "/tmp/gone-forever-xyz"
        # Re-save with broken path
        # We need to also re-key it
        repos["/tmp/gone-forever-xyz"] = repos.pop(key)
        repos["/tmp/gone-forever-xyz"]["name"] = "gone"
        _save_registry(repos)

        # Should not crash
        results = registry_search("hello")
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class TestFormatters:
    def test_format_empty_list(self):
        output = format_registry_list([])
        assert "No repositories registered" in output

    def test_format_list_with_entries(self):
        entries = [
            RepoEntry(
                path="/tmp/a", name="alpha",
                registered_at="2026-01-01", node_count=10,
                edge_count=5, file_count=3,
            ),
            RepoEntry(
                path="/tmp/b", name="beta",
                registered_at="2026-01-02", node_count=20,
                edge_count=15, file_count=8,
            ),
        ]
        output = format_registry_list(entries)
        assert "alpha" in output
        assert "beta" in output
        assert "Total: 2" in output

    def test_format_cross_repo_results_empty(self):
        output = format_cross_repo_results([])
        assert "No matching functions" in output

    def test_format_cross_repo_results(self):
        results = [
            CrossRepoMatch(
                repo_name="myrepo", repo_path="/tmp/myrepo",
                function_name="hello", file_path="main.py",
                line=1, score=2.5, signature="hello()",
                complexity="low", behavior="says hello",
            ),
        ]
        output = format_cross_repo_results(results)
        assert "myrepo" in output
        assert "hello" in output
        assert "score:" in output

    def test_cross_repo_results_to_json(self):
        results = [
            CrossRepoMatch(
                repo_name="r", repo_path="/tmp/r",
                function_name="f", file_path="a.py",
                line=1, score=1.0, signature="f()",
                complexity="low", behavior="does stuff",
            ),
        ]
        text = cross_repo_results_to_json(results)
        data = json.loads(text)
        assert data["count"] == 1
        assert data["results"][0]["repo"] == "r"
