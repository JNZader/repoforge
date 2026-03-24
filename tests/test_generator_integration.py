"""
tests/test_generator_integration.py — Integration tests for the generation pipeline.

Tests the full generate_artifacts pipeline with real filesystem operations.
Only LLM completion calls are mocked.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from repoforge.generator import (
    generate_artifacts,
    _rank_modules,
    _rel,
    _write,
    _generate,
    _update_gitignore,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _git_init(path):
    subprocess.run(["git", "init"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True)


@pytest.fixture
def python_project(tmp_path):
    """Realistic Python project for generation tests."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test-project"\nversion = "1.0.0"\n'
    )
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n")
    (tmp_path / "main.py").write_text(
        '"""Main application."""\n'
        'from fastapi import FastAPI\n\n'
        'app = FastAPI()\n\n'
        'def create_app():\n    return app\n'
    )
    svc = tmp_path / "services"
    svc.mkdir()
    (svc / "__init__.py").write_text("")
    (svc / "user_service.py").write_text(
        '"""User management service."""\n'
        'from pydantic import BaseModel\n\n'
        'class UserService:\n'
        '    def get_user(self, id: int): ...\n'
        '    def create_user(self, data: dict): ...\n'
        '    def delete_user(self, id: int): ...\n'
    )
    (svc / "auth.py").write_text(
        '"""Authentication service."""\n'
        'import jwt\n\n'
        'def authenticate(token: str): ...\n'
        'def authorize(user, permission): ...\n'
        'class AuthMiddleware:\n    pass\n'
    )
    _git_init(tmp_path)
    return tmp_path


@pytest.fixture
def small_project(tmp_path):
    """Tiny project (should classify as small)."""
    (tmp_path / "main.py").write_text(
        '"""Simple script."""\n\ndef main():\n    print("hello")\n'
    )
    _git_init(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Dry-run tests
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_returns_summary(self, python_project):
        result = generate_artifacts(
            working_dir=str(python_project),
            dry_run=True,
            verbose=False,
        )
        assert "skills" in result
        assert "agents" in result
        assert "complexity" in result
        assert len(result["skills"]) > 0

    def test_dry_run_no_files_written(self, python_project):
        generate_artifacts(
            working_dir=str(python_project),
            dry_run=True,
            verbose=False,
        )
        claude_dir = python_project / ".claude"
        # In dry-run, no SKILL.md files should be generated
        skills = list(claude_dir.rglob("SKILL.md")) if claude_dir.exists() else []
        assert len(skills) == 0

    def test_dry_run_with_complexity_override(self, python_project):
        result = generate_artifacts(
            working_dir=str(python_project),
            dry_run=True,
            complexity="large",
            verbose=False,
        )
        assert result["complexity"]["size"] == "large"

    def test_dry_run_small_project(self, small_project):
        result = generate_artifacts(
            working_dir=str(small_project),
            dry_run=True,
            verbose=False,
        )
        cx = result["complexity"]
        assert cx["size"] == "small"
        assert cx["generate_orchestrator"] is False


# ---------------------------------------------------------------------------
# Full generation with mocked LLM
# ---------------------------------------------------------------------------

class TestFullGeneration:
    @patch("repoforge.generator.build_llm")
    def test_generates_skills_and_agents(self, mock_build_llm, python_project):
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        mock_llm.complete.return_value = "# Generated Skill\n\nContent here.\n"
        mock_build_llm.return_value = mock_llm

        result = generate_artifacts(
            working_dir=str(python_project),
            output_dir=".claude",
            also_opencode=False,
            verbose=False,
        )

        assert len(result["skills"]) > 0
        # Verify files actually exist
        for skill_path in result["skills"]:
            assert Path(skill_path).exists()

    @patch("repoforge.generator.build_llm")
    def test_generates_index(self, mock_build_llm, python_project):
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        mock_llm.complete.return_value = "# Content\n"
        mock_build_llm.return_value = mock_llm

        generate_artifacts(
            working_dir=str(python_project),
            also_opencode=False,
            verbose=False,
        )

        index = python_project / ".claude" / "SKILLS_INDEX.md"
        assert index.exists()
        content = index.read_text()
        assert "Skills" in content

    @patch("repoforge.generator.build_llm")
    def test_mirrors_to_opencode(self, mock_build_llm, python_project):
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        mock_llm.complete.return_value = "# Content\n"
        mock_build_llm.return_value = mock_llm

        generate_artifacts(
            working_dir=str(python_project),
            also_opencode=True,
            verbose=False,
        )

        opencode = python_project / ".opencode"
        assert opencode.exists()
        assert (opencode / "skills").exists()

    @patch("repoforge.generator.build_llm")
    def test_creates_skill_registry(self, mock_build_llm, python_project):
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        mock_llm.complete.return_value = "# Content\n"
        mock_build_llm.return_value = mock_llm

        result = generate_artifacts(
            working_dir=str(python_project),
            also_opencode=False,
            verbose=False,
        )

        registry_path = Path(result["registry"])
        assert registry_path.exists()
        assert ".atl" in str(registry_path)

    @patch("repoforge.generator.build_llm")
    def test_disclosure_tiered(self, mock_build_llm, python_project):
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        mock_llm.complete.return_value = "# Content\n"
        mock_build_llm.return_value = mock_llm

        result = generate_artifacts(
            working_dir=str(python_project),
            also_opencode=False,
            disclosure="tiered",
            verbose=False,
        )

        assert result["disclosure"] == "tiered"

    @patch("repoforge.generator.build_llm")
    def test_small_repo_skips_orchestrator(self, mock_build_llm, small_project):
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        mock_llm.complete.return_value = "# Content\n"
        mock_build_llm.return_value = mock_llm

        result = generate_artifacts(
            working_dir=str(small_project),
            also_opencode=False,
            verbose=False,
        )

        # Small repo shouldn't generate orchestrator or layer agents
        agent_files = [a for a in result["agents"] if "orchestrator" in a]
        assert len(agent_files) == 0


# ---------------------------------------------------------------------------
# _rank_modules
# ---------------------------------------------------------------------------

class TestRankModules:
    def test_high_value_ranked_first(self):
        modules = [
            {"name": "index", "path": "src/index.ts", "exports": ["a"] * 10, "summary_hint": ""},
            {"name": "auth", "path": "src/auth.py", "exports": ["login", "logout"], "summary_hint": "Auth module"},
            {"name": "constants", "path": "src/constants.py", "exports": [], "summary_hint": ""},
        ]
        ranked = _rank_modules(modules)
        assert ranked[0]["name"] == "auth"

    def test_test_files_ranked_last(self):
        modules = [
            {"name": "service", "path": "src/service.py", "exports": ["get"], "summary_hint": ""},
            {"name": "test_service", "path": "tests/test_service.py", "exports": ["test_get"], "summary_hint": ""},
        ]
        ranked = _rank_modules(modules)
        assert ranked[-1]["name"] == "test_service"

    def test_more_exports_ranked_higher(self):
        modules = [
            {"name": "few", "path": "few.py", "exports": ["a"], "summary_hint": ""},
            {"name": "many", "path": "many.py", "exports": list("abcdefghij"), "summary_hint": ""},
        ]
        ranked = _rank_modules(modules)
        assert ranked[0]["name"] == "many"

    def test_summary_hint_bonus(self):
        modules = [
            {"name": "a", "path": "a.py", "exports": ["x"], "summary_hint": "Well documented"},
            {"name": "b", "path": "b.py", "exports": ["x"], "summary_hint": ""},
        ]
        ranked = _rank_modules(modules)
        assert ranked[0]["name"] == "a"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_rel_inside_root(self, tmp_path):
        child = tmp_path / "a" / "b.txt"
        assert _rel(child, tmp_path) == "a/b.txt"

    def test_rel_outside_root(self, tmp_path):
        outside = Path("/other/path")
        result = _rel(outside, tmp_path)
        assert "/other/path" in result

    def test_write_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "a" / "b" / "c" / "file.md"
        _write(path, "content", dry_run=False)
        assert path.exists()
        assert path.read_text() == "content"

    def test_write_dry_run_does_nothing(self, tmp_path):
        path = tmp_path / "should_not_exist.md"
        _write(path, "content", dry_run=True)
        assert not path.exists()

    def test_generate_dry_run(self):
        llm = MagicMock()
        llm.model = "test"
        result = _generate(llm, "sys", "user", dry_run=True)
        assert "DRY RUN" in result
        llm.complete.assert_not_called()

    def test_generate_calls_llm(self):
        llm = MagicMock()
        llm.model = "test"
        llm.complete.return_value = "Generated content"
        result = _generate(llm, "sys", "user", dry_run=False)
        assert result == "Generated content"
        llm.complete.assert_called_once()


# ---------------------------------------------------------------------------
# Gitignore update
# ---------------------------------------------------------------------------

class TestUpdateGitignore:
    def test_creates_gitignore(self, tmp_path):
        _update_gitignore(tmp_path, ".atl/")
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        assert ".atl/" in gitignore.read_text()

    def test_appends_to_existing(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n.env\n")
        _update_gitignore(tmp_path, ".atl/")
        content = gitignore.read_text()
        assert "node_modules/" in content
        assert ".atl/" in content

    def test_no_duplicate(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".atl/\n")
        _update_gitignore(tmp_path, ".atl/")
        content = gitignore.read_text()
        assert content.count(".atl/") == 1


# ---------------------------------------------------------------------------
# Config integration
# ---------------------------------------------------------------------------

class TestConfigIntegration:
    def test_repoforge_yaml_model_override(self, python_project):
        (python_project / "repoforge.yaml").write_text("model: gpt-4o-mini\n")
        subprocess.run(["git", "add", "."], cwd=python_project, capture_output=True)
        subprocess.run(["git", "commit", "-m", "cfg"], cwd=python_project, capture_output=True)

        result = generate_artifacts(
            working_dir=str(python_project),
            dry_run=True,
            verbose=False,
        )
        # Dry-run should work without error with config override
        assert len(result["skills"]) > 0

    def test_repoforge_yaml_complexity_override(self, python_project):
        (python_project / "repoforge.yaml").write_text("complexity: large\n")
        subprocess.run(["git", "add", "."], cwd=python_project, capture_output=True)
        subprocess.run(["git", "commit", "-m", "cfg"], cwd=python_project, capture_output=True)

        result = generate_artifacts(
            working_dir=str(python_project),
            dry_run=True,
            verbose=False,
        )
        assert result["complexity"]["size"] == "large"
