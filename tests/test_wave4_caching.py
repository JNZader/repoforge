"""Tests for Wave 4: Caching & Incremental Generation."""

import json
from pathlib import Path

import pytest

from repoforge.cache import (
    CacheStore,
    compute_repo_snapshot,
    diff_snapshots,
    hash_content,
    hash_file,
)

# ── hash functions ───────────────────────────────────────────────────────


class TestHashFunctions:

    def test_hash_content_deterministic(self):
        h1 = hash_content("hello world")
        h2 = hash_content("hello world")
        assert h1 == h2

    def test_hash_content_different_for_different_input(self):
        h1 = hash_content("hello")
        h2 = hash_content("world")
        assert h1 != h2

    def test_hash_content_returns_hex_string(self):
        h = hash_content("test")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_hash_file(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("print('hello')\n")
        h = hash_file(f)
        assert isinstance(h, str)
        assert len(h) == 64

    def test_hash_file_deterministic(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("content")
        assert hash_file(f) == hash_file(f)

    def test_hash_file_matches_content_hash(self, tmp_path):
        content = "print('hello')\n"
        f = tmp_path / "test.py"
        f.write_text(content)
        assert hash_file(f) == hash_content(content)


# ── repo snapshot ────────────────────────────────────────────────────────


class TestRepoSnapshot:

    def _make_repo(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("x = 1\n")
        (tmp_path / "src" / "utils.py").write_text("y = 2\n")
        (tmp_path / "README.md").write_text("# Hello\n")
        return tmp_path

    def test_snapshot_returns_dict(self, tmp_path):
        self._make_repo(tmp_path)
        snap = compute_repo_snapshot(tmp_path)
        assert isinstance(snap, dict)
        assert "files" in snap

    def test_snapshot_contains_file_hashes(self, tmp_path):
        self._make_repo(tmp_path)
        snap = compute_repo_snapshot(tmp_path)
        files = snap["files"]
        assert "src/app.py" in files
        assert "src/utils.py" in files
        assert len(files["src/app.py"]) == 64  # SHA-256

    def test_snapshot_deterministic(self, tmp_path):
        self._make_repo(tmp_path)
        s1 = compute_repo_snapshot(tmp_path)
        s2 = compute_repo_snapshot(tmp_path)
        assert s1 == s2

    def test_snapshot_changes_when_file_changes(self, tmp_path):
        self._make_repo(tmp_path)
        s1 = compute_repo_snapshot(tmp_path)
        (tmp_path / "src" / "app.py").write_text("x = 999\n")
        s2 = compute_repo_snapshot(tmp_path)
        assert s1["files"]["src/app.py"] != s2["files"]["src/app.py"]
        assert s1["files"]["src/utils.py"] == s2["files"]["src/utils.py"]


# ── diff snapshots ───────────────────────────────────────────────────────


class TestDiffSnapshots:

    def test_no_changes(self):
        snap = {"files": {"a.py": "abc123", "b.py": "def456"}}
        diff = diff_snapshots(snap, snap)
        assert diff["added"] == []
        assert diff["removed"] == []
        assert diff["modified"] == []

    def test_detect_added(self):
        old = {"files": {"a.py": "abc123"}}
        new = {"files": {"a.py": "abc123", "b.py": "def456"}}
        diff = diff_snapshots(old, new)
        assert "b.py" in diff["added"]

    def test_detect_removed(self):
        old = {"files": {"a.py": "abc123", "b.py": "def456"}}
        new = {"files": {"a.py": "abc123"}}
        diff = diff_snapshots(old, new)
        assert "b.py" in diff["removed"]

    def test_detect_modified(self):
        old = {"files": {"a.py": "abc123"}}
        new = {"files": {"a.py": "xyz789"}}
        diff = diff_snapshots(old, new)
        assert "a.py" in diff["modified"]

    def test_mixed_changes(self):
        old = {"files": {"a.py": "aaa", "b.py": "bbb", "c.py": "ccc"}}
        new = {"files": {"a.py": "aaa", "b.py": "BBB", "d.py": "ddd"}}
        diff = diff_snapshots(old, new)
        assert diff["added"] == ["d.py"]
        assert diff["removed"] == ["c.py"]
        assert diff["modified"] == ["b.py"]

    def test_diff_against_empty_old(self):
        new = {"files": {"a.py": "aaa", "b.py": "bbb"}}
        diff = diff_snapshots({"files": {}}, new)
        assert sorted(diff["added"]) == ["a.py", "b.py"]


# ── CacheStore persistence ───────────────────────────────────────────────


class TestCacheStore:

    def test_save_and_load(self, tmp_path):
        store = CacheStore(tmp_path / ".repoforge-cache.json")
        store.save_snapshot({"files": {"a.py": "abc"}})
        loaded = store.load_snapshot()
        assert loaded == {"files": {"a.py": "abc"}}

    def test_load_returns_none_when_no_cache(self, tmp_path):
        store = CacheStore(tmp_path / ".repoforge-cache.json")
        assert store.load_snapshot() is None

    def test_save_llm_response(self, tmp_path):
        store = CacheStore(tmp_path / ".repoforge-cache.json")
        prompt_hash = hash_content("system+user prompt text")
        store.save_llm_response(prompt_hash, "Generated content here")
        assert store.get_llm_response(prompt_hash) == "Generated content here"

    def test_llm_response_miss(self, tmp_path):
        store = CacheStore(tmp_path / ".repoforge-cache.json")
        assert store.get_llm_response("nonexistent") is None

    def test_cache_file_created(self, tmp_path):
        store = CacheStore(tmp_path / ".repoforge-cache.json")
        store.save_snapshot({"files": {}})
        assert (tmp_path / ".repoforge-cache.json").exists()

    def test_overwrite_existing_cache(self, tmp_path):
        store = CacheStore(tmp_path / ".repoforge-cache.json")
        store.save_snapshot({"files": {"a.py": "old"}})
        store.save_snapshot({"files": {"a.py": "new"}})
        loaded = store.load_snapshot()
        assert loaded["files"]["a.py"] == "new"
