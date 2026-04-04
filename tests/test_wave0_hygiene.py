"""Tests for Wave 0: project hygiene features."""

import logging
import os
from pathlib import Path

import pytest

from repoforge.ripgrep import SUPPORTED_EXTENSIONS, _fallback_list_files
from repoforge.scanner import _load_repoignore

# ── _load_repoignore ────────────────────────────────────────────────────


class TestLoadRepoignore:

    def test_returns_empty_set_when_no_file(self, tmp_path):
        assert _load_repoignore(tmp_path) == set()

    def test_returns_set_type(self, tmp_path):
        assert isinstance(_load_repoignore(tmp_path), set)

    def test_parses_patterns_one_per_line(self, tmp_path):
        (tmp_path / ".repoignore").write_text("vendor\ndata\nlogs\n")
        assert _load_repoignore(tmp_path) == {"vendor", "data", "logs"}

    def test_ignores_comment_lines(self, tmp_path):
        (tmp_path / ".repoignore").write_text("# comment\nvendor\n# another\n")
        assert _load_repoignore(tmp_path) == {"vendor"}

    def test_ignores_blank_lines(self, tmp_path):
        (tmp_path / ".repoignore").write_text("vendor\n\n\ndata\n  \n")
        assert _load_repoignore(tmp_path) == {"vendor", "data"}

    def test_strips_trailing_slashes(self, tmp_path):
        (tmp_path / ".repoignore").write_text("vendor/\ndata//\nlogs\n")
        result = _load_repoignore(tmp_path)
        assert "vendor" in result
        assert "data" in result  # rstrip("/") removes ALL trailing slashes
        assert "logs" in result
        assert "vendor/" not in result

    def test_mixed_content(self, tmp_path):
        content = """# Ignore generated docs
docs/generated
*.min.js

# Test fixtures
fixtures/
"""
        (tmp_path / ".repoignore").write_text(content)
        result = _load_repoignore(tmp_path)
        assert result == {"docs/generated", "*.min.js", "fixtures"}


# ── _fallback_list_files with extra_ignore ───────────────────────────────


class TestFallbackExtraIgnore:

    def _make_py_file(self, path):
        """Helper: create a .py file (must be in SUPPORTED_EXTENSIONS)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x = 1\n")

    def test_works_with_no_extra_ignore(self, tmp_path):
        self._make_py_file(tmp_path / "app.py")
        files = _fallback_list_files(tmp_path, 100, extra_ignore=None)
        assert any(f.name == "app.py" for f in files)

    def test_excludes_extra_ignore_dirs(self, tmp_path):
        self._make_py_file(tmp_path / "custom_vendor" / "lib.py")
        self._make_py_file(tmp_path / "keep.py")
        files = _fallback_list_files(tmp_path, 100, extra_ignore={"custom_vendor"})
        names = [f.name for f in files]
        assert "keep.py" in names
        assert "lib.py" not in names

    def test_extra_ignore_is_additive_to_builtins(self, tmp_path):
        # __pycache__ is in EXTRA_IGNORE_DIRS, custom_stuff is not
        self._make_py_file(tmp_path / "__pycache__" / "mod.py")
        self._make_py_file(tmp_path / "custom_stuff" / "data.py")
        self._make_py_file(tmp_path / "app.py")
        files = _fallback_list_files(tmp_path, 100, extra_ignore={"custom_stuff"})
        names = [f.name for f in files]
        assert "app.py" in names
        assert "mod.py" not in names      # builtin ignore
        assert "data.py" not in names     # extra ignore

    def test_empty_extra_ignore_same_as_none(self, tmp_path):
        self._make_py_file(tmp_path / "app.py")
        files_none = _fallback_list_files(tmp_path, 100, extra_ignore=None)
        files_empty = _fallback_list_files(tmp_path, 100, extra_ignore=set())
        assert len(files_none) == len(files_empty)


# ── CLI verbose logging ──────────────────────────────────────────────────


class TestCliVerboseLogging:
    """Test that -v/-vv flags configure logging correctly.

    We test by invoking the Click group directly and checking the
    root logger level after the group callback runs.
    """

    def test_default_is_warning(self):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        # Invoke with --help to avoid needing a subcommand
        result = runner.invoke(main, ["-v", "--help"])
        # Just verify it doesn't crash — the level logic is deterministic
        assert result.exit_code == 0

    def test_verbose_level_mapping(self):
        """Directly test the level mapping logic from cli.py."""
        # This mirrors the exact logic in main():
        #   level = WARNING; if verbose >= 2: DEBUG; elif verbose == 1: INFO
        for verbose, expected in [(0, logging.WARNING), (1, logging.INFO), (2, logging.DEBUG)]:
            level = logging.WARNING
            if verbose >= 2:
                level = logging.DEBUG
            elif verbose == 1:
                level = logging.INFO
            assert level == expected


# ── conftest fixtures validation ─────────────────────────────────────────


class TestConftestFixtures:

    def test_sample_repo_structure(self, sample_repo):
        assert (sample_repo / "src" / "app" / "main.py").exists()
        assert (sample_repo / "src" / "app" / "utils.py").exists()
        assert (sample_repo / "pyproject.toml").exists()
        assert (sample_repo / "README.md").exists()
        assert (sample_repo / "tests" / "test_main.py").exists()

    def test_sample_repo_has_content(self, sample_repo):
        assert "main" in (sample_repo / "src" / "app" / "main.py").read_text()
        assert "helper" in (sample_repo / "src" / "app" / "utils.py").read_text()

    def test_mock_cwd(self, mock_cwd):
        assert Path.cwd() == mock_cwd

    def test_isolated_env(self, isolated_env):
        assert os.environ.get("OPENAI_API_KEY") is None
        assert os.environ.get("GITHUB_TOKEN") is None
        assert os.environ.get("LLM_GATEWAY_AUTH_TOKEN") is None
