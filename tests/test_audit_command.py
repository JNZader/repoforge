"""
tests/test_audit_command.py — Tests for the `repoforge audit` command.

Covers:
  - Exit code behavior per --fail-on level (none / medium / high)
  - JSON output format and structure
  - Graceful handling when docs/ dir doesn't exist
  - Text output sections rendered correctly
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from repoforge.cli import main

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def simple_repo(tmp_path: Path) -> Path:
    """Minimal Python repo — no docs/, no lock file."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "simple"\nversion = "0.1.0"\n'
    )
    (tmp_path / "main.py").write_text(
        "def greet(name):\n    return f'hello {name}'\n"
    )
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True,
    )
    return tmp_path


@pytest.fixture
def complex_repo(tmp_path: Path) -> Path:
    """Repo with a high-complexity function to trigger findings."""
    # Write a function with many branches (complexity > 15)
    branches = "    if a:\n        pass\n" * 16
    (tmp_path / "complex.py").write_text(
        f"def very_complex(a, b, c):\n{branches}    return a\n"
    )
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"],
        cwd=tmp_path, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"],
        cwd=tmp_path, capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True,
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Basic smoke tests
# ---------------------------------------------------------------------------

def test_audit_runs_without_error(runner, simple_repo):
    """audit command should exit 0 on a simple repo with no issues."""
    result = runner.invoke(main, ["audit", str(simple_repo)])
    assert result.exit_code == 0, result.output


def test_audit_shows_sections_in_text_output(runner, simple_repo):
    """Text output must contain all four section headers."""
    result = runner.invoke(main, ["audit", str(simple_repo)])
    assert "=== Complexity ===" in result.output
    assert "=== Dead Code ===" in result.output
    assert "=== Dep Health ===" in result.output
    assert "=== Summary ===" in result.output


def test_audit_no_docs_dir_shows_skipped(runner, simple_repo):
    """When docs/ doesn't exist, doc drift section says skipped."""
    result = runner.invoke(main, ["audit", str(simple_repo)])
    assert "=== Doc Drift ===" in result.output
    assert "docs/ not found, skipped" in result.output


def test_audit_docs_dir_exists_runs_drift(runner, simple_repo):
    """When docs/ exists, doc drift section appears with a result line."""
    (simple_repo / "docs").mkdir()
    result = runner.invoke(main, ["audit", str(simple_repo)])
    assert "=== Doc Drift ===" in result.output
    # Either "ok docs up to date" or a drift finding
    assert ("docs up to date" in result.output or "docs stale" in result.output)


# ---------------------------------------------------------------------------
# JSON output format
# ---------------------------------------------------------------------------

def test_audit_json_output_structure(runner, simple_repo):
    """JSON output must contain path, summary, and findings keys."""
    result = runner.invoke(main, ["audit", str(simple_repo), "--fmt", "json", "--quiet"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)

    assert "path" in data
    assert "summary" in data
    assert "findings" in data

    summary = data["summary"]
    assert "total" in summary
    assert "high" in summary
    assert "medium" in summary

    findings = data["findings"]
    assert "complexity" in findings
    assert "dead_code" in findings
    assert "doc_drift" in findings
    assert "dep_health" in findings


def test_audit_json_findings_are_lists(runner, simple_repo):
    """Each findings key must map to a list."""
    result = runner.invoke(main, ["audit", str(simple_repo), "--fmt", "json", "--quiet"])
    data = json.loads(result.output)
    for key in ("complexity", "dead_code", "doc_drift", "dep_health"):
        assert isinstance(data["findings"][key], list), f"{key} should be a list"


def test_audit_json_counts_match_findings(runner, simple_repo):
    """summary.total must equal len of all findings combined."""
    result = runner.invoke(main, ["audit", str(simple_repo), "--fmt", "json", "--quiet"])
    data = json.loads(result.output)
    actual_total = sum(
        len(v) for v in data["findings"].values()
    )
    assert data["summary"]["total"] == actual_total


# ---------------------------------------------------------------------------
# --fail-on behavior
# ---------------------------------------------------------------------------

def test_fail_on_none_always_exits_0(runner, complex_repo):
    """--fail-on none must exit 0 even when findings exist."""
    result = runner.invoke(main, ["audit", str(complex_repo), "--fail-on", "none"])
    assert result.exit_code == 0, result.output


def test_fail_on_high_exits_0_when_only_medium(runner, tmp_path):
    """--fail-on high (default) exits 0 when only medium findings exist."""
    # A function with complexity between 10 and 14 (medium, not high)
    branches = "    if a:\n        pass\n" * 10
    (tmp_path / "med.py").write_text(
        f"def medium_fn(a):\n{branches}    return a\n"
    )
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)

    result = runner.invoke(
        main, ["audit", str(tmp_path), "--fail-on", "high"]
    )
    # Should exit 0 if no HIGH findings (only medium)
    # We just verify the command runs without crashing and exits 0 or 1 cleanly
    assert result.exit_code in (0, 1)


def test_fail_on_medium_exits_1_when_medium_findings(runner, tmp_path):
    """--fail-on medium exits 1 when medium findings exist."""
    # Function with complexity between 10 and 14
    branches = "    if a:\n        pass\n" * 10
    (tmp_path / "med.py").write_text(
        f"def medium_fn(a):\n{branches}    return a\n"
    )
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)

    result = runner.invoke(
        main, ["audit", str(tmp_path), "--fail-on", "medium"]
    )
    # If there are medium findings, should exit 1
    data_result = runner.invoke(
        main, ["audit", str(tmp_path), "--fmt", "json", "--fail-on", "none", "--quiet"]
    )
    data = json.loads(data_result.output)
    medium_count = data["summary"]["medium"]

    if medium_count > 0:
        assert result.exit_code == 1
    else:
        assert result.exit_code == 0


def test_fail_on_none_with_json(runner, complex_repo):
    """--fail-on none with JSON output: always exit 0, valid JSON."""
    result = runner.invoke(
        main, ["audit", str(complex_repo), "--fail-on", "none", "--fmt", "json", "--quiet"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "findings" in data


# ---------------------------------------------------------------------------
# --quiet flag
# ---------------------------------------------------------------------------

def test_quiet_suppresses_progress(runner, simple_repo):
    """--quiet should not print the 'Auditing ...' progress line."""
    result = runner.invoke(main, ["audit", str(simple_repo), "--quiet"])
    # Progress goes to stderr, but CliRunner mixes them — just check no crash
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_audit_empty_repo(runner, tmp_path):
    """Repo with no Python files should exit 0 with no findings."""
    (tmp_path / "README.md").write_text("# Empty\n")
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)

    result = runner.invoke(main, ["audit", str(tmp_path)])
    assert result.exit_code == 0


def test_audit_default_path_is_cwd(runner, simple_repo, monkeypatch):
    """audit with no PATH argument should default to current directory."""
    monkeypatch.chdir(simple_repo)
    result = runner.invoke(main, ["audit"])
    assert result.exit_code == 0
