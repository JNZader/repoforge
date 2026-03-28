"""Tests for Wave 10: CI integration — git diff, drift detection, quality gate."""

import json
from pathlib import Path

import pytest

from repoforge.ci import (
    detect_changed_files,
    detect_doc_drift,
    quality_gate,
    DriftReport,
    GateResult,
)


# ── detect_changed_files ─────────────────────────────────────────────────


class TestDetectChangedFiles:

    def _init_repo(self, tmp_path):
        """Create a minimal git repo with initial commit."""
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
        (tmp_path / "app.py").write_text("x = 1\n")
        (tmp_path / "utils.py").write_text("y = 2\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init", "--no-verify"], cwd=tmp_path, capture_output=True)
        return tmp_path

    def test_no_changes_returns_empty(self, tmp_path):
        self._init_repo(tmp_path)
        changed = detect_changed_files(tmp_path)
        assert changed == []

    def test_detects_modified_file(self, tmp_path):
        self._init_repo(tmp_path)
        (tmp_path / "app.py").write_text("x = 999\n")
        changed = detect_changed_files(tmp_path)
        assert "app.py" in changed

    def test_detects_new_file(self, tmp_path):
        self._init_repo(tmp_path)
        (tmp_path / "new.py").write_text("z = 3\n")
        changed = detect_changed_files(tmp_path)
        assert "new.py" in changed

    def test_returns_relative_paths(self, tmp_path):
        self._init_repo(tmp_path)
        (tmp_path / "app.py").write_text("changed\n")
        changed = detect_changed_files(tmp_path)
        for f in changed:
            assert not f.startswith("/")


# ── detect_doc_drift ─────────────────────────────────────────────────────


class TestDetectDocDrift:

    def test_no_drift_when_fresh(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("x = 1\n")
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "01-overview.md").write_text("# Overview\n")

        report = detect_doc_drift(tmp_path, docs_dir=docs)
        assert isinstance(report, DriftReport)

    def test_drift_report_has_fields(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("x = 1\n")
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "01-overview.md").write_text("# Overview\n")

        report = detect_doc_drift(tmp_path, docs_dir=docs)
        assert hasattr(report, "is_stale")
        assert hasattr(report, "source_hash")
        assert hasattr(report, "docs_hash")
        assert hasattr(report, "changed_sources")

    def test_detects_drift_after_source_change(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("x = 1\n")
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "01-overview.md").write_text("# Overview\n")

        # First check — save state
        report1 = detect_doc_drift(tmp_path, docs_dir=docs)
        old_hash = report1.source_hash

        # Change source
        (src / "app.py").write_text("x = 999\n")

        report2 = detect_doc_drift(tmp_path, docs_dir=docs)
        assert report2.source_hash != old_hash


# ── quality_gate ─────────────────────────────────────────────────────────


class TestQualityGate:

    def test_passes_with_good_docs(self, tmp_path):
        good = """# Architecture

## Overview

The system uses a layered architecture.

## Components

| Component | Purpose |
|-----------|---------|
| API | HTTP endpoints |
| Store | Data persistence |

## Data Flow

```mermaid
graph LR
    A --> B --> C
```

## Decisions

- **SQLite**: Embedded database.

```python
def main():
    pass
```
"""
        (tmp_path / "01-overview.md").write_text(good)
        result = quality_gate(str(tmp_path), threshold=0.4)
        assert isinstance(result, GateResult)
        assert result.passed is True

    def test_fails_with_weak_docs(self, tmp_path):
        (tmp_path / "01-overview.md").write_text("# Stuff\n\nHello.\n")
        result = quality_gate(str(tmp_path), threshold=0.8)
        assert result.passed is False

    def test_gate_result_has_scores(self, tmp_path):
        (tmp_path / "01-overview.md").write_text("# Test\n\nContent here.\n")
        result = quality_gate(str(tmp_path), threshold=0.5)
        assert hasattr(result, "scores")
        assert hasattr(result, "min_score")
        assert hasattr(result, "threshold")

    def test_empty_dir_passes(self, tmp_path):
        result = quality_gate(str(tmp_path), threshold=0.5)
        assert result.passed is True  # nothing to fail

    def test_exit_code(self, tmp_path):
        (tmp_path / "01-overview.md").write_text("# Stuff\n\nHello.\n")
        result = quality_gate(str(tmp_path), threshold=0.9)
        assert result.exit_code == 1
        result2 = quality_gate(str(tmp_path), threshold=0.01)
        assert result2.exit_code == 0
