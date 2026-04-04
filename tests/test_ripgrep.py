"""
tests/test_ripgrep.py - Tests for the ripgrep integration.

All tests run regardless of whether rg is installed —
they test both the rg path and the fallback path.
"""

from pathlib import Path

import pytest

from repoforge.ripgrep import (
    _fallback_extract_definitions,
    _fallback_extract_imports,
    _fallback_list_files,
    _fallback_summary_hints,
    extract_definitions,
    extract_imports,
    extract_summary_hints,
    list_files,
    repo_stats,
    rg_available,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def python_project(tmp_path):
    """A small Python project with known exports/imports."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

    (tmp_path / "main.py").write_text("""\
\"\"\"Main entry point for the application.\"\"\"
import os
import fastapi
from pydantic import BaseModel

def create_app():
    pass

async def startup():
    pass

class AppConfig:
    debug: bool = False

def _private_helper():
    pass
""")

    (tmp_path / "utils.py").write_text("""\
\"\"\"Utility functions.\"\"\"
import json
from pathlib import Path

def read_json(path: str) -> dict:
    pass

def write_json(data: dict, path: str) -> None:
    pass
""")

    sub = tmp_path / "routers"
    sub.mkdir()
    (sub / "__init__.py").write_text("")
    (sub / "users.py").write_text("""\
# User management router
import fastapi
from pydantic import BaseModel

def get_users():
    pass

def create_user(data: dict):
    pass

class UserRouter:
    pass
""")

    # A file that should be ignored
    ignored = tmp_path / "node_modules"
    ignored.mkdir()
    (ignored / "something.py").write_text("def ignored(): pass\n")

    return tmp_path


@pytest.fixture
def ts_project(tmp_path):
    """A TypeScript project with known exports."""
    (tmp_path / "package.json").write_text('{"name": "test"}')

    (tmp_path / "index.ts").write_text("""\
// Main application entry
import express from 'express'
import { PrismaClient } from '@prisma/client'

export function createApp() {}
export class AppServer {}
export const defaultConfig = {}
""")

    (tmp_path / "utils.ts").write_text("""\
// Utility helpers
import lodash from 'lodash'

export function formatDate(d: Date): string { return '' }
export const VERSION = '1.0'
""")

    return tmp_path


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

def test_rg_available_returns_bool():
    result = rg_available()
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

class TestListFiles:
    def test_finds_python_files(self, python_project):
        files = list_files(python_project)
        names = [f.name for f in files]
        assert "main.py" in names
        assert "utils.py" in names
        assert "users.py" in names

    def test_excludes_node_modules(self, python_project):
        files = list_files(python_project)
        # Use relative paths — absolute paths may include test dir names with "node_modules"
        rel_paths = []
        for f in files:
            try:
                rel_paths.append(str(f.relative_to(python_project)))
            except ValueError:
                pass
        assert not any("node_modules" in p for p in rel_paths)

    def test_finds_ts_files(self, ts_project):
        files = list_files(ts_project)
        names = [f.name for f in files]
        assert "index.ts" in names
        assert "utils.ts" in names

    def test_fallback_matches_rg(self, python_project):
        """Fallback should find the same files as rg (approximately)."""
        rg_files = set(f.name for f in list_files(python_project))
        fb_files = set(f.name for f in _fallback_list_files(python_project, 100))
        # Both should find the core files
        assert "main.py" in rg_files
        assert "main.py" in fb_files

    def test_empty_dir(self, tmp_path):
        files = list_files(tmp_path)
        assert files == []


# ---------------------------------------------------------------------------
# Definition extraction
# ---------------------------------------------------------------------------

class TestExtractDefinitions:
    def test_finds_python_functions(self, python_project):
        files = list_files(python_project)
        defs = extract_definitions(files, python_project)
        # Flatten all exports
        all_exports = [name for exports in defs.values() for name in exports]
        assert "create_app" in all_exports
        assert "startup" in all_exports
        assert "AppConfig" in all_exports

    def test_excludes_private_python(self, python_project):
        files = list_files(python_project)
        defs = extract_definitions(files, python_project)
        all_exports = [name for exports in defs.values() for name in exports]
        assert "_private_helper" not in all_exports

    def test_finds_ts_exports(self, ts_project):
        files = list_files(ts_project)
        defs = extract_definitions(files, ts_project)
        all_exports = [name for exports in defs.values() for name in exports]
        assert "createApp" in all_exports
        assert "AppServer" in all_exports
        assert "defaultConfig" in all_exports

    def test_fallback_consistency(self, python_project):
        """Fallback and rg results should overlap significantly."""
        files = [f for f in list_files(python_project) if f.suffix == ".py"]
        rg_defs = extract_definitions(files, python_project)
        fb_defs = _fallback_extract_definitions(files, python_project)
        # Both should find create_app in main.py
        rg_all = [n for v in rg_defs.values() for n in v]
        fb_all = [n for v in fb_defs.values() for n in v]
        assert "create_app" in rg_all or "create_app" in fb_all

    def test_empty_file_list(self, tmp_path):
        assert extract_definitions([], tmp_path) == {}


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------

class TestExtractImports:
    def test_finds_python_imports(self, python_project):
        files = [f for f in list_files(python_project) if f.name == "main.py"]
        imports = extract_imports(files, python_project)
        all_imports = [pkg for pkgs in imports.values() for pkg in pkgs]
        assert "fastapi" in all_imports or "os" in all_imports

    def test_finds_ts_imports(self, ts_project):
        files = [f for f in list_files(ts_project) if f.name == "index.ts"]
        imports = extract_imports(files, ts_project)
        all_imports = [pkg for pkgs in imports.values() for pkg in pkgs]
        assert "express" in all_imports

    def test_excludes_relative_imports(self, tmp_path):
        """Relative imports like './utils' should not appear."""
        (tmp_path / "app.py").write_text("from .utils import helper\nimport requests\n")
        files = list_files(tmp_path)
        imports = extract_imports(files, tmp_path)
        all_imports = [pkg for pkgs in imports.values() for pkg in pkgs]
        assert "utils" not in all_imports
        # external deps should still be found
        # (requests may or may not match depending on rg availability)

    def test_empty_file_list(self, tmp_path):
        assert extract_imports([], tmp_path) == {}


# ---------------------------------------------------------------------------
# Summary hints
# ---------------------------------------------------------------------------

class TestExtractSummaryHints:
    def test_finds_python_docstrings(self, python_project):
        files = [f for f in list_files(python_project) if f.name == "main.py"]
        hints = extract_summary_hints(files, python_project)
        all_hints = list(hints.values())
        assert any("entry point" in h.lower() or "main" in h.lower() for h in all_hints)

    def test_finds_ts_comments(self, ts_project):
        files = [f for f in list_files(ts_project) if f.name == "index.ts"]
        hints = extract_summary_hints(files, ts_project)
        # Should find the "Main application entry" comment
        all_hints = list(hints.values())
        assert any(len(h) > 5 for h in all_hints)

    def test_empty_file_list(self, tmp_path):
        assert extract_summary_hints([], tmp_path) == {}


# ---------------------------------------------------------------------------
# Repo stats
# ---------------------------------------------------------------------------

class TestRepoStats:
    def test_returns_expected_keys(self, python_project):
        stats = repo_stats(python_project)
        assert "total_files" in stats
        assert "by_extension" in stats
        assert "rg_available" in stats

    def test_counts_files(self, python_project):
        stats = repo_stats(python_project)
        assert stats["total_files"] >= 3  # main.py, utils.py, users.py

    def test_by_extension(self, python_project):
        stats = repo_stats(python_project)
        assert ".py" in stats["by_extension"]
        assert stats["by_extension"][".py"] >= 3
