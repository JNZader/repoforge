"""
tests/test_docs_generator_integration.py — Integration tests for docs generation pipeline.

Tests the full generate_docs pipeline with real filesystem operations.
Only the LLM completion calls are mocked.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repoforge.docs_generator import (
    _infer_project_name,
    _make_logger,
    _prettify_name,
    _rel,
    generate_docs,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def python_repo(tmp_path):
    """Create a realistic Python project."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "my-awesome-api"\nversion = "1.0.0"\n'
    )
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\npydantic\n")
    (tmp_path / "main.py").write_text(
        '"""FastAPI application entry point."""\n'
        'from fastapi import FastAPI\n\napp = FastAPI()\n'
    )
    src = tmp_path / "src"
    src.mkdir()
    (src / "models.py").write_text(
        '"""Data models."""\nfrom pydantic import BaseModel\n\n'
        'class User(BaseModel):\n    name: str\n'
    )
    (src / "routes.py").write_text(
        '"""API routes."""\nfrom fastapi import APIRouter\n\n'
        'router = APIRouter()\n\n'
        '@router.get("/users")\ndef get_users(): ...\n'
    )
    # git init for scanner
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    return tmp_path


@pytest.fixture
def node_repo(tmp_path):
    """Create a minimal Node.js project."""
    (tmp_path / "package.json").write_text(
        '{"name": "cool-frontend", "dependencies": {"react": "18"}}'
    )
    (tmp_path / "index.ts").write_text(
        '// Main entry\nexport default function App() { return "hello"; }\n'
    )
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    return tmp_path


@pytest.fixture
def go_repo(tmp_path):
    """Create a minimal Go project."""
    (tmp_path / "go.mod").write_text("module github.com/user/my-service\n\ngo 1.21\n")
    (tmp_path / "main.go").write_text(
        'package main\n\nimport "fmt"\n\nfunc main() { fmt.Println("hello") }\n'
    )
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    return tmp_path


# ---------------------------------------------------------------------------
# Project name inference
# ---------------------------------------------------------------------------

class TestInferProjectName:
    def test_from_pyproject(self, python_repo):
        from repoforge.scanner import scan_repo
        repo_map = scan_repo(str(python_repo))
        name = _infer_project_name(python_repo, repo_map)
        assert "Awesome" in name or "awesome" in name.lower()

    def test_from_package_json(self, node_repo):
        from repoforge.scanner import scan_repo
        repo_map = scan_repo(str(node_repo))
        name = _infer_project_name(node_repo, repo_map)
        assert "cool" in name.lower() or "frontend" in name.lower()

    def test_from_go_mod(self, go_repo):
        from repoforge.scanner import scan_repo
        repo_map = scan_repo(str(go_repo))
        name = _infer_project_name(go_repo, repo_map)
        assert "service" in name.lower()

    def test_fallback_to_dir_name(self, tmp_path):
        from repoforge.scanner import scan_repo
        repo_map = scan_repo(str(tmp_path))
        name = _infer_project_name(tmp_path, repo_map)
        assert len(name) > 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_prettify_kebab(self):
        assert _prettify_name("my-cool-project") == "My Cool Project"

    def test_prettify_snake(self):
        assert _prettify_name("my_cool_project") == "My Cool Project"

    def test_prettify_simple(self):
        assert _prettify_name("project") == "Project"

    def test_rel_inside_root(self, tmp_path):
        child = tmp_path / "a" / "b.txt"
        result = _rel(child, tmp_path)
        assert result == "a/b.txt"

    def test_rel_outside_root(self, tmp_path):
        outside = Path("/some/other/path")
        result = _rel(outside, tmp_path)
        assert "/some/other/path" in result

    def test_make_logger_verbose(self, capsys):
        log = _make_logger(True)
        log("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.err

    def test_make_logger_quiet(self, capsys):
        log = _make_logger(False)
        log("should not appear")
        captured = capsys.readouterr()
        assert captured.err == ""


# ---------------------------------------------------------------------------
# Dry-run (no LLM calls at all)
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_returns_chapters(self, python_repo):
        result = generate_docs(
            working_dir=str(python_repo),
            output_dir=str(python_repo / "docs"),
            dry_run=True,
            verbose=False,
        )
        assert result["dry_run"] is True
        assert len(result["chapters"]) > 0
        assert result["language"] == "English"

    def test_dry_run_no_files_written(self, python_repo):
        docs_dir = python_repo / "docs"
        generate_docs(
            working_dir=str(python_repo),
            output_dir=str(docs_dir),
            dry_run=True,
            verbose=False,
        )
        assert not docs_dir.exists()

    def test_dry_run_with_spanish(self, python_repo):
        result = generate_docs(
            working_dir=str(python_repo),
            output_dir=str(python_repo / "docs"),
            dry_run=True,
            language="Spanish",
            verbose=False,
        )
        assert result["language"] == "Spanish"

    def test_dry_run_with_project_name(self, python_repo):
        result = generate_docs(
            working_dir=str(python_repo),
            output_dir=str(python_repo / "docs"),
            dry_run=True,
            project_name="Override Name",
            verbose=False,
        )
        assert result["project_name"] == "Override Name"

    def test_dry_run_complexity_small(self, python_repo):
        result = generate_docs(
            working_dir=str(python_repo),
            output_dir=str(python_repo / "docs"),
            dry_run=True,
            complexity="small",
            verbose=False,
        )
        assert len(result["chapters"]) <= 5


# ---------------------------------------------------------------------------
# Full generation with mocked LLM
# ---------------------------------------------------------------------------

class TestFullGeneration:
    @patch("repoforge.model_router.build_llm")
    def test_generates_chapters_and_docsify(self, mock_build_llm, python_repo):
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        mock_llm.complete.return_value = "# Test Chapter\n\nGenerated content.\n"
        mock_build_llm.return_value = mock_llm

        docs_dir = python_repo / "test_docs"
        result = generate_docs(
            working_dir=str(python_repo),
            output_dir=str(docs_dir),
            verbose=False,
        )

        assert docs_dir.exists()
        assert len(result["chapters_generated"]) > 0
        assert len(result["docsify_files"]) >= 3  # sidebar, nojekyll, index.html

        # Verify docsify files
        assert (docs_dir / "index.html").exists()
        assert (docs_dir / "_sidebar.md").exists()
        assert (docs_dir / ".nojekyll").exists()

        # Verify at least one chapter was written
        md_files = list(docs_dir.glob("*.md"))
        assert len(md_files) >= 2  # _sidebar + at least one chapter

    @patch("repoforge.model_router.build_llm")
    def test_llm_error_captured(self, mock_build_llm, python_repo):
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        mock_llm.complete.side_effect = Exception("LLM failed")
        mock_build_llm.return_value = mock_llm

        docs_dir = python_repo / "err_docs"
        result = generate_docs(
            working_dir=str(python_repo),
            output_dir=str(docs_dir),
            verbose=False,
        )

        assert len(result["errors"]) > 0
        assert result["errors"][0]["error"] == "LLM failed"

    @patch("repoforge.model_router.build_llm")
    def test_output_dir_created(self, mock_build_llm, python_repo):
        mock_llm = MagicMock()
        mock_llm.model = "test"
        mock_llm.complete.return_value = "# Content\n"
        mock_build_llm.return_value = mock_llm

        deep_dir = python_repo / "a" / "b" / "c" / "docs"
        generate_docs(
            working_dir=str(python_repo),
            output_dir=str(deep_dir),
            verbose=False,
        )
        assert deep_dir.exists()


# ---------------------------------------------------------------------------
# Config overrides (repoforge.yaml)
# ---------------------------------------------------------------------------

class TestConfigOverrides:
    def test_config_language_override(self, python_repo):
        (python_repo / "repoforge.yaml").write_text("language: Spanish\n")
        # re-init git to include the config
        subprocess.run(["git", "add", "."], cwd=python_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "cfg"], cwd=python_repo, capture_output=True)

        result = generate_docs(
            working_dir=str(python_repo),
            output_dir=str(python_repo / "docs"),
            dry_run=True,
            verbose=False,
        )
        assert result["language"] == "Spanish"

    def test_config_project_name_override(self, python_repo):
        (python_repo / "repoforge.yaml").write_text('project_name: "Custom Name"\n')
        subprocess.run(["git", "add", "."], cwd=python_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "cfg"], cwd=python_repo, capture_output=True)

        result = generate_docs(
            working_dir=str(python_repo),
            output_dir=str(python_repo / "docs"),
            dry_run=True,
            verbose=False,
        )
        assert result["project_name"] == "Custom Name"
