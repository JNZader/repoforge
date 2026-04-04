"""Tests for Wave 12: Advanced documentation generators."""

import subprocess
from pathlib import Path

import pytest

from repoforge.facts import FactItem
from repoforge.generators import (
    generate_api_reference,
    generate_changelog,
    generate_onboarding,
)
from repoforge.intelligence.ast_extractor import ASTSymbol

# ── helpers ──────────────────────────────────────────────────────────────


def _init_repo_with_history(tmp_path):
    """Create a git repo with several commits."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    (tmp_path / "app.py").write_text("v1\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: initial release", "--no-verify"],
                   cwd=tmp_path, capture_output=True)

    (tmp_path / "app.py").write_text("v2\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "fix: resolve startup crash", "--no-verify"],
                   cwd=tmp_path, capture_output=True)

    (tmp_path / "utils.py").write_text("helper\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: add utility module", "--no-verify"],
                   cwd=tmp_path, capture_output=True)

    return tmp_path


def _sample_facts():
    return [
        FactItem(fact_type="endpoint", value="GET /health", file="server.py", line=10, language="Python"),
        FactItem(fact_type="endpoint", value="POST /api/users", file="server.py", line=25, language="Python"),
        FactItem(fact_type="endpoint", value="GET /api/users/:id", file="server.py", line=40, language="Python"),
        FactItem(fact_type="port", value="8080", file="server.py", line=5, language="Python"),
        FactItem(fact_type="env_var", value="DATABASE_URL", file="config.py", line=3, language="Python"),
    ]


def _sample_symbols():
    return {
        "server.py": [
            ASTSymbol(name="health_check", kind="function", signature="def health_check() -> dict",
                      return_type="dict", file="server.py", line=10),
            ASTSymbol(name="create_user", kind="function", signature="def create_user(data: UserCreate) -> User",
                      params=["data: UserCreate"], return_type="User", file="server.py", line=25),
            ASTSymbol(name="get_user", kind="function", signature="def get_user(user_id: int) -> User",
                      params=["user_id: int"], return_type="User", file="server.py", line=40),
        ],
        "models.py": [
            ASTSymbol(name="User", kind="class", signature="class User(BaseModel)",
                      fields=["id: int", "name: str", "email: str"], file="models.py", line=5),
            ASTSymbol(name="UserCreate", kind="class", signature="class UserCreate(BaseModel)",
                      fields=["name: str", "email: str"], file="models.py", line=15),
        ],
    }


def _sample_repo_map():
    return {
        "tech_stack": ["Python", "FastAPI"],
        "entry_points": ["server.py"],
        "config_files": ["pyproject.toml"],
        "layers": {
            "main": {
                "path": ".",
                "modules": [
                    {"path": "server.py", "name": "server", "language": "Python",
                     "exports": ["health_check", "create_user", "get_user"]},
                    {"path": "models.py", "name": "models", "language": "Python",
                     "exports": ["User", "UserCreate"]},
                ],
            },
        },
    }


# ── generate_changelog ───────────────────────────────────────────────────


class TestGenerateChangelog:

    def test_generates_markdown(self, tmp_path):
        _init_repo_with_history(tmp_path)
        changelog = generate_changelog(tmp_path)
        assert isinstance(changelog, str)
        assert len(changelog) > 0

    def test_contains_commit_messages(self, tmp_path):
        _init_repo_with_history(tmp_path)
        changelog = generate_changelog(tmp_path)
        assert "initial release" in changelog
        assert "startup crash" in changelog
        assert "utility module" in changelog

    def test_groups_by_type(self, tmp_path):
        _init_repo_with_history(tmp_path)
        changelog = generate_changelog(tmp_path)
        # Should have sections for feat/fix
        assert "feat" in changelog.lower() or "feature" in changelog.lower() or "added" in changelog.lower()

    def test_max_commits_limits_output(self, tmp_path):
        _init_repo_with_history(tmp_path)
        changelog = generate_changelog(tmp_path, max_commits=1)
        # Should only show the most recent commit
        assert "utility module" in changelog
        assert "initial release" not in changelog

    def test_no_git_returns_empty(self, tmp_path):
        # Not a git repo
        changelog = generate_changelog(tmp_path)
        assert changelog == ""


# ── generate_api_reference ───────────────────────────────────────────────


class TestGenerateApiReference:

    def test_generates_markdown(self):
        result = generate_api_reference(
            facts=_sample_facts(), ast_symbols=_sample_symbols(),
        )
        assert isinstance(result, str)
        assert "# API Reference" in result

    def test_lists_endpoints(self):
        result = generate_api_reference(
            facts=_sample_facts(), ast_symbols=_sample_symbols(),
        )
        assert "GET /health" in result
        assert "POST /api/users" in result

    def test_includes_handler_signatures(self):
        result = generate_api_reference(
            facts=_sample_facts(), ast_symbols=_sample_symbols(),
        )
        assert "health_check" in result or "create_user" in result

    def test_includes_models(self):
        result = generate_api_reference(
            facts=_sample_facts(), ast_symbols=_sample_symbols(),
        )
        assert "User" in result

    def test_empty_facts_returns_minimal(self):
        result = generate_api_reference(facts=[], ast_symbols={})
        assert result == "" or "No API" in result


# ── generate_onboarding ─────────────────────────────────────────────────


class TestGenerateOnboarding:

    def test_generates_markdown(self):
        result = generate_onboarding(
            repo_map=_sample_repo_map(), project_name="TestProject",
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_project_name(self):
        result = generate_onboarding(
            repo_map=_sample_repo_map(), project_name="MyApp",
        )
        assert "MyApp" in result

    def test_contains_tech_stack(self):
        result = generate_onboarding(
            repo_map=_sample_repo_map(), project_name="TestProject",
        )
        assert "Python" in result or "FastAPI" in result

    def test_contains_getting_started_section(self):
        result = generate_onboarding(
            repo_map=_sample_repo_map(), project_name="TestProject",
        )
        lower = result.lower()
        assert "getting started" in lower or "quick start" in lower or "setup" in lower

    def test_lists_entry_points(self):
        result = generate_onboarding(
            repo_map=_sample_repo_map(), project_name="TestProject",
        )
        assert "server.py" in result

    def test_empty_repo_map_returns_minimal(self):
        result = generate_onboarding(
            repo_map={"tech_stack": [], "entry_points": [], "config_files": [], "layers": {}},
            project_name="Empty",
        )
        assert "Empty" in result
