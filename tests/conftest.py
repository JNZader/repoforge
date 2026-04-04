"""Shared fixtures for the repoforge test suite."""

import os
from pathlib import Path

import pytest


@pytest.fixture
def sample_repo(tmp_path):
    """Create a minimal Python repo structure for integration tests.

    Provides: pyproject.toml, README.md, src/app/main.py, src/app/utils.py,
    tests/test_main.py — enough for scanner, graph, and doc generation tests.
    """
    # pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "sample-project"\nversion = "1.0.0"\n'
        'requires-python = ">=3.10"\n\n'
        "[project.scripts]\nsample = \"app.main:main\"\n"
    )

    # README
    (tmp_path / "README.md").write_text("# Sample Project\n\nA test project.\n")

    # Source
    src = tmp_path / "src" / "app"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text('"""Sample app."""\n')
    (src / "main.py").write_text(
        '"""Main entry point."""\n'
        "from .utils import helper\n\n\n"
        "def main():\n"
        '    print(helper("world"))\n'
    )
    (src / "utils.py").write_text(
        '"""Utility functions."""\n\n\n'
        "def helper(name: str) -> str:\n"
        '    return f"Hello, {name}!"\n'
    )

    # Tests
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_main.py").write_text(
        "from app.utils import helper\n\n\n"
        "def test_helper():\n"
        '    assert helper("x") == "Hello, x!"\n'
    )

    return tmp_path


@pytest.fixture
def mock_cwd(tmp_path, monkeypatch):
    """Monkeypatch Path.cwd() to return tmp_path."""
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def isolated_env(monkeypatch):
    """Clear environment variables that affect repoforge behavior."""
    for var in (
        "OPENAI_API_KEY",
        "GITHUB_TOKEN",
        "REPOFORGE_MODEL",
        "REPOFORGE_API_KEY",
        "REPOFORGE_API_BASE",
    ):
        monkeypatch.delenv(var, raising=False)
