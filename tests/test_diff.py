"""Tests for repoforge.diff — entity-level semantic diffs."""

import json
import subprocess
from unittest.mock import patch

import pytest

from repoforge.diff import (
    DiffEntry,
    DiffResult,
    _body_hash,
    _match_symbols,
    _normalize_body,
    diff_entities,
    render_diff_json,
    render_diff_markdown,
    render_diff_table,
)
from repoforge.symbols.extractor import Symbol

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo(tmp_path):
    """Create a real git repo with two commits for integration tests."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def _run(*args):
        subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, check=True,
        )

    _run("init", "-b", "main")
    _run("config", "user.email", "test@test.com")
    _run("config", "user.name", "Test")

    # Commit A: two functions
    (repo / "app.py").write_text(
        'def hello():\n    return "hello"\n\n\n'
        'def greet(name):\n    return f"hi {name}"\n'
    )
    _run("add", ".")
    _run("commit", "-m", "initial")
    _run("tag", "v1")

    # Commit B: modify hello, remove greet, add farewell, rename nothing yet
    (repo / "app.py").write_text(
        'def hello():\n    return "hello world"\n\n\n'
        'def farewell(name):\n    return f"bye {name}"\n'
    )
    _run("add", ".")
    _run("commit", "-m", "changes")
    _run("tag", "v2")

    return repo


@pytest.fixture
def git_repo_rename(tmp_path):
    """Create a git repo where a function is renamed (same body)."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def _run(*args):
        subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, check=True,
        )

    _run("init", "-b", "main")
    _run("config", "user.email", "test@test.com")
    _run("config", "user.name", "Test")

    (repo / "utils.py").write_text(
        'def old_name(x):\n    return x + 1\n'
    )
    _run("add", ".")
    _run("commit", "-m", "initial")
    _run("tag", "v1")

    (repo / "utils.py").write_text(
        'def new_name(x):\n    return x + 1\n'
    )
    _run("add", ".")
    _run("commit", "-m", "rename")
    _run("tag", "v2")

    return repo


@pytest.fixture
def git_repo_cosmetic(tmp_path):
    """Create a git repo with only cosmetic changes (whitespace)."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def _run(*args):
        subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, check=True,
        )

    _run("init", "-b", "main")
    _run("config", "user.email", "test@test.com")
    _run("config", "user.name", "Test")

    (repo / "mod.py").write_text(
        'def compute(x):\n    return x * 2\n'
    )
    _run("add", ".")
    _run("commit", "-m", "initial")
    _run("tag", "v1")

    # Only whitespace change
    (repo / "mod.py").write_text(
        'def compute(x):\n    return  x  *  2\n'
    )
    _run("add", ".")
    _run("commit", "-m", "whitespace")
    _run("tag", "v2")

    return repo


# ---------------------------------------------------------------------------
# Unit tests: _normalize_body
# ---------------------------------------------------------------------------


class TestNormalizeBody:
    def test_strips_comments(self):
        content = "def foo():\n    # a comment\n    return 1\n"
        result = _normalize_body(content, 1, 3)
        assert "# a comment" not in result
        assert "return 1" in result

    def test_collapses_whitespace(self):
        content = "def foo():\n    return   1\n"
        result = _normalize_body(content, 1, 2)
        # Internal whitespace runs should be collapsed to single space
        assert "return   1" not in result
        assert "return 1" in result

    def test_empty_content(self):
        result = _normalize_body("", 1, 1)
        assert result == ""


# ---------------------------------------------------------------------------
# Unit tests: _match_symbols
# ---------------------------------------------------------------------------


class TestMatchSymbols:
    def test_added_symbol(self):
        symbols_a = []
        symbols_b = [Symbol("foo", "function", "a.py", 1, 3)]
        entries = _match_symbols(symbols_a, symbols_b, None, None)
        assert len(entries) == 1
        assert entries[0].status == "added"
        assert entries[0].name == "foo"

    def test_removed_symbol(self):
        symbols_a = [Symbol("bar", "function", "a.py", 1, 3)]
        symbols_b = []
        entries = _match_symbols(symbols_a, symbols_b, None, None)
        assert len(entries) == 1
        assert entries[0].status == "removed"
        assert entries[0].name == "bar"

    def test_modified_symbol_logic(self):
        content_a = "def foo():\n    return 1\n"
        content_b = "def foo():\n    return 2\n"
        symbols_a = [Symbol("foo", "function", "a.py", 1, 2)]
        symbols_b = [Symbol("foo", "function", "a.py", 1, 2)]
        entries = _match_symbols(symbols_a, symbols_b, content_a, content_b)
        assert len(entries) == 1
        assert entries[0].status == "modified"
        assert entries[0].change_type == "logic"

    def test_identical_symbols_no_entry(self):
        content = "def foo():\n    return 1\n"
        symbols_a = [Symbol("foo", "function", "a.py", 1, 2)]
        symbols_b = [Symbol("foo", "function", "a.py", 1, 2)]
        entries = _match_symbols(symbols_a, symbols_b, content, content)
        assert len(entries) == 0

    def test_rename_detection(self):
        content_a = "def old_fn():\n    return 42\n"
        content_b = "def new_fn():\n    return 42\n"
        symbols_a = [Symbol("old_fn", "function", "a.py", 1, 2)]
        symbols_b = [Symbol("new_fn", "function", "a.py", 1, 2)]
        entries = _match_symbols(symbols_a, symbols_b, content_a, content_b)
        renamed = [e for e in entries if e.status == "renamed"]
        # Body after skipping declaration is "return 42" in both → rename detected
        assert len(renamed) == 1
        assert renamed[0].name == "new_fn"
        assert renamed[0].old_name == "old_fn"


# ---------------------------------------------------------------------------
# Unit tests: DiffResult properties
# ---------------------------------------------------------------------------


class TestDiffResult:
    def test_summary(self):
        result = DiffResult(
            ref_a="a", ref_b="b",
            entries=[
                DiffEntry("f1", "function", "a.py", "added"),
                DiffEntry("f2", "function", "a.py", "removed"),
                DiffEntry("f3", "function", "a.py", "modified", change_type="logic"),
                DiffEntry("f4", "function", "a.py", "renamed", old_name="f0"),
            ],
        )
        assert result.summary == {
            "added": 1, "removed": 1, "modified": 1, "renamed": 1, "total": 4,
        }

    def test_property_filters(self):
        result = DiffResult(
            ref_a="a", ref_b="b",
            entries=[
                DiffEntry("f1", "function", "a.py", "added"),
                DiffEntry("f2", "function", "a.py", "added"),
                DiffEntry("f3", "function", "a.py", "removed"),
            ],
        )
        assert len(result.added) == 2
        assert len(result.removed) == 1
        assert len(result.modified) == 0
        assert len(result.renamed) == 0


# ---------------------------------------------------------------------------
# Unit tests: Renderers
# ---------------------------------------------------------------------------


class TestRenderers:
    @pytest.fixture
    def sample_result(self):
        return DiffResult(
            ref_a="v1", ref_b="v2",
            entries=[
                DiffEntry("foo", "function", "app.py", "added", line=5),
                DiffEntry("bar", "function", "app.py", "removed", line=1),
                DiffEntry("baz", "function", "app.py", "modified", change_type="logic", line=10),
                DiffEntry("qux", "function", "app.py", "renamed", old_name="quux", line=15),
            ],
        )

    def test_render_table(self, sample_result):
        output = render_diff_table(sample_result)
        assert "v1" in output
        assert "v2" in output
        assert "foo" in output
        assert "added" in output
        assert "Summary:" in output

    def test_render_table_empty(self):
        result = DiffResult(ref_a="a", ref_b="b")
        output = render_diff_table(result)
        assert "No entity-level changes" in output

    def test_render_json(self, sample_result):
        output = render_diff_json(sample_result)
        data = json.loads(output)
        assert data["ref_a"] == "v1"
        assert data["ref_b"] == "v2"
        assert len(data["entries"]) == 4
        assert data["summary"]["added"] == 1

    def test_render_markdown(self, sample_result):
        output = render_diff_markdown(sample_result)
        assert "# Entity Diff:" in output
        assert "| added |" in output
        assert "`foo`" in output
        assert "was: `quux`" in output

    def test_render_markdown_empty(self):
        result = DiffResult(ref_a="a", ref_b="b")
        output = render_diff_markdown(result)
        assert "No entity-level changes" in output


# ---------------------------------------------------------------------------
# Integration tests: diff_entities with real git repo
# ---------------------------------------------------------------------------


class TestDiffEntitiesIntegration:
    def test_basic_diff(self, git_repo):
        result = diff_entities(str(git_repo), "v1", "v2")
        names = {e.name: e.status for e in result.entries}
        assert "hello" in names
        assert names["hello"] == "modified"
        # greet removed, farewell added
        assert "greet" in names
        assert names["greet"] == "removed"
        assert "farewell" in names
        assert names["farewell"] == "added"

    def test_rename_detection(self, git_repo_rename):
        result = diff_entities(str(git_repo_rename), "v1", "v2")
        renamed = result.renamed
        assert len(renamed) == 1
        assert renamed[0].name == "new_name"
        assert renamed[0].old_name == "old_name"

    def test_cosmetic_change(self, git_repo_cosmetic):
        result = diff_entities(str(git_repo_cosmetic), "v1", "v2")
        if result.entries:
            for e in result.entries:
                if e.status == "modified":
                    assert e.change_type == "cosmetic"

    def test_invalid_ref(self, git_repo):
        with pytest.raises(RuntimeError, match="git command failed"):
            diff_entities(str(git_repo), "nonexistent", "HEAD")


# ---------------------------------------------------------------------------
# CLI integration test
# ---------------------------------------------------------------------------


class TestDiffCLI:
    def test_diff_command_help(self):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["diff", "--help"])
        assert result.exit_code == 0
        assert "Entity-level semantic diff" in result.output

    def test_diff_command_runs(self, git_repo):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["diff", "v1", "v2", "-w", str(git_repo)])
        assert result.exit_code == 0
        assert "hello" in result.output

    def test_diff_command_json(self, git_repo):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "diff", "v1", "v2", "-w", str(git_repo), "--format", "json", "-q",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "entries" in data

    def test_diff_command_invalid_ref(self, git_repo):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "diff", "nonexistent", "HEAD", "-w", str(git_repo),
        ])
        assert result.exit_code != 0
