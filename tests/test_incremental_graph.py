"""Tests for incremental_graph module — item #21."""

import json
from pathlib import Path

import pytest

from repoforge.incremental_graph import (
    CACHE_FILENAME,
    build_graph_incremental,
    get_cache_info,
    invalidate_cache,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def python_project(tmp_path):
    """Create a minimal Python project for graph building."""
    (tmp_path / "models.py").write_text(
        "class User:\n    pass\n"
    )
    (tmp_path / "service.py").write_text(
        "from models import User\n\ndef get_user():\n    return User()\n"
    )
    (tmp_path / "api.py").write_text(
        "from service import get_user\n\ndef handler():\n    return get_user()\n"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestBuildGraphIncremental:
    def test_first_run_creates_cache(self, python_project):
        graph, stats = build_graph_incremental(str(python_project))
        assert not stats["cached"]
        assert stats["total_files"] >= 3
        # Cache file should exist
        cache_path = python_project / CACHE_FILENAME
        assert cache_path.exists()

    def test_second_run_uses_cache(self, python_project):
        # First run
        build_graph_incremental(str(python_project))
        # Second run — no changes
        graph, stats = build_graph_incremental(str(python_project))
        assert stats["cached"]
        assert stats["changed_files"] == []
        assert stats["build_time_ms"] >= 0

    def test_modification_triggers_rebuild(self, python_project):
        # First run
        build_graph_incremental(str(python_project))
        # Modify a file
        (python_project / "models.py").write_text(
            "class User:\n    pass\n\nclass NewModel:\n    pass\n"
        )
        # Second run — should detect change
        graph, stats = build_graph_incremental(str(python_project))
        assert not stats["cached"]

    def test_new_file_triggers_rebuild(self, python_project):
        build_graph_incremental(str(python_project))
        # Add a new file
        (python_project / "utils.py").write_text("def helper(): pass\n")
        graph, stats = build_graph_incremental(str(python_project))
        assert not stats["cached"]

    def test_force_rebuild(self, python_project):
        build_graph_incremental(str(python_project))
        graph, stats = build_graph_incremental(str(python_project), force=True)
        assert not stats["cached"]

    def test_graph_has_nodes(self, python_project):
        graph, _ = build_graph_incremental(str(python_project))
        node_ids = [n.id for n in graph.nodes]
        assert "models.py" in node_ids
        assert "service.py" in node_ids


class TestInvalidateCache:
    def test_invalidate_existing(self, python_project):
        build_graph_incremental(str(python_project))
        assert invalidate_cache(str(python_project))
        assert not (python_project / CACHE_FILENAME).exists()

    def test_invalidate_nonexistent(self, python_project):
        assert not invalidate_cache(str(python_project))


class TestGetCacheInfo:
    def test_info_after_build(self, python_project):
        build_graph_incremental(str(python_project))
        info = get_cache_info(str(python_project))
        assert info is not None
        assert info["version"] == 1
        assert info["file_count"] >= 3
        assert info["node_count"] >= 3

    def test_info_no_cache(self, python_project):
        info = get_cache_info(str(python_project))
        assert info is None

    def test_corrupt_cache(self, python_project):
        (python_project / CACHE_FILENAME).write_text("not json")
        info = get_cache_info(str(python_project))
        assert info is None
