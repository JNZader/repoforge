"""Tests for decision_intel_v2 — decision registry with git history and staleness."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repoforge.decision_intel_v2 import (
    DecisionEntry,
    DecisionRegistry,
    _extract_decisions_from_commits,
    build_decision_registry,
    format_decision_registry,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def git_project(tmp_path):
    """Create a temp git project with decision markers."""
    subprocess.run(
        ["git", "init"], cwd=str(tmp_path),
        capture_output=True, timeout=10,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path),
        capture_output=True, timeout=10,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=str(tmp_path),
        capture_output=True, timeout=10,
    )

    # Create files with decision markers
    (tmp_path / "auth.py").write_text(
        "# WHY: JWT chosen over sessions for horizontal scaling\n"
        "import jwt\n"
        "\n"
        "# DECISION: RS256 over HS256 for asymmetric key support\n"
        "ALGORITHM = 'RS256'\n"
        "\n"
        "def verify_token(token):\n"
        "    # TRADEOFF: slower verification but better security\n"
        "    return jwt.decode(token, algorithms=[ALGORITHM])\n"
    )

    (tmp_path / "db.py").write_text(
        "# DECISION: PostgreSQL for JSONB support and CTEs\n"
        "DATABASE_URL = 'postgresql://localhost/app'\n"
    )

    subprocess.run(
        ["git", "add", "."], cwd=str(tmp_path),
        capture_output=True, timeout=10,
    )
    subprocess.run(
        ["git", "commit", "-m", "feat: initial setup\n\nWHY: monorepo for shared types"],
        cwd=str(tmp_path), capture_output=True, timeout=10,
    )

    return tmp_path


# ---------------------------------------------------------------------------
# DecisionEntry data model
# ---------------------------------------------------------------------------


class TestDecisionEntry:
    def test_confidence_high(self):
        e = DecisionEntry(
            marker="WHY", text="reason", file="a.py", line=1,
            source="inline", lines_changed_since=5,
        )
        assert e.confidence == "high"

    def test_confidence_medium(self):
        e = DecisionEntry(
            marker="WHY", text="reason", file="a.py", line=1,
            source="inline", lines_changed_since=20,
        )
        assert e.confidence == "medium"

    def test_confidence_low(self):
        e = DecisionEntry(
            marker="WHY", text="reason", file="a.py", line=1,
            source="inline", lines_changed_since=60,
        )
        assert e.confidence == "low"

    def test_confidence_stale_overrides(self):
        e = DecisionEntry(
            marker="WHY", text="reason", file="a.py", line=1,
            source="inline", lines_changed_since=5, is_stale=True,
        )
        assert e.confidence == "stale"


# ---------------------------------------------------------------------------
# DecisionRegistry data model
# ---------------------------------------------------------------------------


class TestDecisionRegistry:
    def _build_registry(self) -> DecisionRegistry:
        return DecisionRegistry(
            entries=[
                DecisionEntry("WHY", "reason one", "auth.py", 1, "inline"),
                DecisionEntry("DECISION", "reason two", "auth.py", 4, "inline",
                              is_stale=True, staleness_reason="100 lines changed"),
                DecisionEntry("WHY", "reason three", "db.py", 1, "inline"),
                DecisionEntry("TRADEOFF", "reason four", "auth.py", 8, "commit",
                              commit_sha="abc12345"),
            ],
            commits_analyzed=100,
            files_scanned=5,
        )

    def test_stale_decisions(self):
        reg = self._build_registry()
        stale = reg.stale_decisions
        assert len(stale) == 1
        assert stale[0].text == "reason two"

    def test_by_file(self):
        reg = self._build_registry()
        by_file = reg.by_file
        assert len(by_file["auth.py"]) == 3
        assert len(by_file["db.py"]) == 1

    def test_by_marker(self):
        reg = self._build_registry()
        by_marker = reg.by_marker
        assert len(by_marker["WHY"]) == 2
        assert len(by_marker["DECISION"]) == 1
        assert len(by_marker["TRADEOFF"]) == 1

    def test_by_source(self):
        reg = self._build_registry()
        by_source = reg.by_source
        assert len(by_source["inline"]) == 3
        assert len(by_source["commit"]) == 1


# ---------------------------------------------------------------------------
# Git-based extraction
# ---------------------------------------------------------------------------


class TestCommitExtraction:
    def test_extracts_from_commit_messages(self, git_project):
        entries = _extract_decisions_from_commits(str(git_project), max_commits=50)
        # Should find "WHY: monorepo for shared types" from commit message
        assert len(entries) >= 1
        assert any(e.marker == "WHY" and "monorepo" in e.text for e in entries)

    def test_empty_repo_returns_empty(self, tmp_path):
        entries = _extract_decisions_from_commits(str(tmp_path), max_commits=10)
        assert entries == []


# ---------------------------------------------------------------------------
# Full registry building
# ---------------------------------------------------------------------------


class TestBuildRegistry:
    def test_builds_from_git_project(self, git_project):
        registry = build_decision_registry(str(git_project), max_commits=50)
        assert registry.files_scanned > 0
        assert len(registry.entries) > 0

    def test_finds_inline_markers(self, git_project):
        registry = build_decision_registry(
            str(git_project), include_commits=False,
        )
        inline = [e for e in registry.entries if e.source == "inline"]
        assert len(inline) >= 3  # WHY, DECISION, TRADEOFF in auth.py + DECISION in db.py

    def test_finds_commit_decisions(self, git_project):
        registry = build_decision_registry(str(git_project), max_commits=50)
        commit_entries = [e for e in registry.entries if e.source == "commit"]
        assert len(commit_entries) >= 1

    def test_no_commits_flag(self, git_project):
        registry = build_decision_registry(
            str(git_project), include_commits=False,
        )
        commit_entries = [e for e in registry.entries if e.source == "commit"]
        assert len(commit_entries) == 0

    def test_stale_only_filter(self, git_project):
        registry = build_decision_registry(
            str(git_project), stale_only=True, stale_threshold=0,
        )
        # With threshold=0, everything with any change is stale
        # New repo may have 0 changes, so just verify the filter works
        for e in registry.entries:
            assert e.is_stale

    def test_author_populated(self, git_project):
        registry = build_decision_registry(
            str(git_project), include_commits=False,
        )
        inline = [e for e in registry.entries if e.source == "inline"]
        # At least some should have author from blame
        authors = [e.author for e in inline if e.author]
        assert len(authors) > 0


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


class TestFormatRegistry:
    def test_format_basic(self):
        registry = DecisionRegistry(
            entries=[
                DecisionEntry("WHY", "reason one", "auth.py", 1, "inline",
                              author="dev", date="2024-01-01"),
                DecisionEntry("DECISION", "reason two", "db.py", 1, "inline",
                              is_stale=True, staleness_reason="50 lines changed"),
            ],
            commits_analyzed=100,
            files_scanned=5,
        )
        output = format_decision_registry(registry)
        assert "## Decision Registry" in output
        assert "Total decisions" in output
        assert "Stale Decisions" in output
        assert "reason two" in output
        assert "auth.py" in output

    def test_format_empty(self):
        registry = DecisionRegistry()
        output = format_decision_registry(registry)
        assert "No decisions found" in output

    def test_format_stale_only(self):
        registry = DecisionRegistry(
            entries=[
                DecisionEntry("WHY", "active", "a.py", 1, "inline"),
                DecisionEntry("WHY", "stale", "b.py", 1, "inline",
                              is_stale=True, staleness_reason="changed"),
            ],
        )
        output = format_decision_registry(registry, stale_only=True)
        assert "stale" in output.lower()

    def test_format_includes_source_info(self):
        registry = DecisionRegistry(
            entries=[
                DecisionEntry("WHY", "from commit", "a.py", 0, "commit",
                              author="dev", date="2024-01-01", commit_sha="abc123"),
            ],
        )
        output = format_decision_registry(registry)
        assert "commit" in output
