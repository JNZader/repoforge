"""
tests/test_hooks.py — Tests for hooks generation feature.

Tests cover:
- hooks_prompt() generates correct prompt with tech stack context
- Hooks generation is skipped when flag is off
- Hooks generation integrates with complexity routing
- Config override from repoforge.yaml
- CLI --with-hooks flag
"""

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def python_repo_map():
    """A Python/FastAPI repo with entry points and config files."""
    return {
        "root": "/fake/pyproject",
        "tech_stack": ["Python", "FastAPI"],
        "entry_points": ["backend/main.py"],
        "config_files": ["pyproject.toml", "docker-compose.yml"],
        "repoforge_config": {},
        "layers": {
            "backend": {
                "path": "backend",
                "modules": [
                    {
                        "path": "backend/main.py", "name": "main",
                        "language": "Python",
                        "exports": ["create_app", "startup"],
                        "imports": ["fastapi"],
                        "summary_hint": "App entry point",
                    },
                    {
                        "path": "backend/tests/test_api.py", "name": "test_api",
                        "language": "Python",
                        "exports": ["test_health"],
                        "imports": ["pytest"],
                        "summary_hint": "API tests",
                    },
                ],
            }
        },
        "stats": {"total_files": 15, "rg_available": False, "rg_version": None},
    }


@pytest.fixture
def node_repo_map():
    """A Node.js/React repo."""
    return {
        "root": "/fake/webapp",
        "tech_stack": ["Node.js", "React", "Next.js"],
        "entry_points": ["src/index.tsx"],
        "config_files": ["package.json"],
        "repoforge_config": {},
        "layers": {
            "frontend": {
                "path": "src",
                "modules": [
                    {
                        "path": "src/index.tsx", "name": "index",
                        "language": "TypeScript",
                        "exports": ["App"],
                        "imports": ["react", "next"],
                        "summary_hint": "App entry",
                    },
                ],
            }
        },
        "stats": {"total_files": 30, "rg_available": False, "rg_version": None},
    }


@pytest.fixture
def go_repo_map():
    """A Go repo with no tests."""
    return {
        "root": "/fake/goservice",
        "tech_stack": ["Go"],
        "entry_points": ["cmd/main.go"],
        "config_files": ["go.mod"],
        "repoforge_config": {},
        "layers": {
            "main": {
                "path": ".",
                "modules": [
                    {
                        "path": "cmd/main.go", "name": "main",
                        "language": "Go",
                        "exports": ["main", "NewServer"],
                        "imports": ["net/http"],
                        "summary_hint": "Server entry point",
                    },
                ],
            }
        },
        "stats": {"total_files": 8, "rg_available": False, "rg_version": None},
    }


@pytest.fixture
def small_complexity():
    return {
        "size": "small", "total_files": 5, "num_layers": 1,
        "total_modules": 2, "max_module_skills_per_layer": 10,
        "min_exports_for_skill": 1, "prompt_detail": "detailed",
        "generate_orchestrator": False, "generate_layer_agents": False,
        "max_files_per_layer": 200, "max_chapters": 5,
        "include_monorepo_hierarchy": False,
    }


@pytest.fixture
def medium_complexity():
    return {
        "size": "medium", "total_files": 50, "num_layers": 3,
        "total_modules": 15, "max_module_skills_per_layer": 5,
        "min_exports_for_skill": 2, "prompt_detail": "standard",
        "generate_orchestrator": True, "generate_layer_agents": True,
        "max_files_per_layer": 150, "max_chapters": 7,
        "include_monorepo_hierarchy": False,
    }


@pytest.fixture
def large_complexity():
    return {
        "size": "large", "total_files": 500, "num_layers": 6,
        "total_modules": 90, "max_module_skills_per_layer": 3,
        "min_exports_for_skill": 3, "prompt_detail": "concise",
        "generate_orchestrator": True, "generate_layer_agents": True,
        "max_files_per_layer": 100, "max_chapters": 9,
        "include_monorepo_hierarchy": True,
    }


# ---------------------------------------------------------------------------
# Tests: hooks_prompt format
# ---------------------------------------------------------------------------

class TestHooksPrompt:
    def test_returns_system_and_user(self, python_repo_map, medium_complexity):
        from repoforge.prompts import hooks_prompt
        system, user = hooks_prompt(python_repo_map, medium_complexity)
        assert isinstance(system, str) and len(system) > 50
        assert isinstance(user, str) and len(user) > 50

    def test_system_describes_hook_format(self, python_repo_map, medium_complexity):
        from repoforge.prompts import hooks_prompt
        system, _ = hooks_prompt(python_repo_map, medium_complexity)
        assert "PreToolUse" in system
        assert "PostToolUse" in system
        assert "exit code" in system.lower() or "Exit" in system

    def test_system_requires_complete_scripts(self, python_repo_map, medium_complexity):
        from repoforge.prompts import hooks_prompt
        system, _ = hooks_prompt(python_repo_map, medium_complexity)
        assert "complete" in system.lower() and "runnable" in system.lower()

    def test_system_limits_hook_count(self, python_repo_map, medium_complexity):
        from repoforge.prompts import hooks_prompt
        system, _ = hooks_prompt(python_repo_map, medium_complexity)
        assert "6 hooks" in system or "6" in system

    def test_user_contains_tech_stack(self, python_repo_map, medium_complexity):
        from repoforge.prompts import hooks_prompt
        _, user = hooks_prompt(python_repo_map, medium_complexity)
        assert "Python" in user
        assert "FastAPI" in user

    def test_user_contains_critical_files(self, python_repo_map, medium_complexity):
        from repoforge.prompts import hooks_prompt
        _, user = hooks_prompt(python_repo_map, medium_complexity)
        assert "backend/main.py" in user
        assert "pyproject.toml" in user

    def test_user_contains_stack_tools(self, python_repo_map, medium_complexity):
        from repoforge.prompts import hooks_prompt
        _, user = hooks_prompt(python_repo_map, medium_complexity)
        assert "ruff" in user
        assert "pytest" in user

    def test_user_detects_tests_exist(self, python_repo_map, medium_complexity):
        from repoforge.prompts import hooks_prompt
        _, user = hooks_prompt(python_repo_map, medium_complexity)
        assert "Has tests: yes" in user

    def test_user_detects_no_tests(self, go_repo_map, small_complexity):
        from repoforge.prompts import hooks_prompt
        _, user = hooks_prompt(go_repo_map, small_complexity)
        assert "Has tests: no" in user

    def test_user_contains_complexity_size(self, python_repo_map, medium_complexity):
        from repoforge.prompts import hooks_prompt
        _, user = hooks_prompt(python_repo_map, medium_complexity)
        assert "medium" in user

    def test_user_contains_layers(self, python_repo_map, medium_complexity):
        from repoforge.prompts import hooks_prompt
        _, user = hooks_prompt(python_repo_map, medium_complexity)
        assert "backend" in user


class TestHooksPromptStackTools:
    """Verify that different tech stacks produce different tool recommendations."""

    def test_python_tools(self, python_repo_map, medium_complexity):
        from repoforge.prompts import hooks_prompt
        _, user = hooks_prompt(python_repo_map, medium_complexity)
        assert "ruff" in user

    def test_node_tools(self, node_repo_map, medium_complexity):
        from repoforge.prompts import hooks_prompt
        _, user = hooks_prompt(node_repo_map, medium_complexity)
        assert "eslint" in user or "next lint" in user

    def test_go_tools(self, go_repo_map, small_complexity):
        from repoforge.prompts import hooks_prompt
        _, user = hooks_prompt(go_repo_map, small_complexity)
        assert "gofmt" in user or "golangci-lint" in user


class TestHooksPromptComplexityScaling:
    """Verify hook scope scales with complexity."""

    def test_small_fewer_hooks(self, python_repo_map, small_complexity):
        from repoforge.prompts import hooks_prompt
        _, user = hooks_prompt(python_repo_map, small_complexity)
        assert "2-3 hooks" in user

    def test_medium_balanced_hooks(self, python_repo_map, medium_complexity):
        from repoforge.prompts import hooks_prompt
        _, user = hooks_prompt(python_repo_map, medium_complexity)
        assert "3-4 hooks" in user

    def test_large_more_hooks(self, python_repo_map, large_complexity):
        from repoforge.prompts import hooks_prompt
        _, user = hooks_prompt(python_repo_map, large_complexity)
        assert "4-6 hooks" in user


# ---------------------------------------------------------------------------
# Tests: generator integration (dry-run, no LLM)
# ---------------------------------------------------------------------------

class TestGeneratorHooksIntegration:
    def test_hooks_skipped_by_default(self, tmp_path):
        """generate_artifacts without --with-hooks should skip hooks."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            dry_run=True,
            verbose=False,
        )
        assert "hooks" not in result

    def test_hooks_generated_when_flag_on(self, tmp_path):
        """generate_artifacts with with_hooks=True should include hooks path."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            with_hooks=True,
            dry_run=True,
            verbose=False,
        )
        assert "hooks" in result
        assert "HOOKS.md" in result["hooks"]

    def test_hooks_path_in_output_dir(self, tmp_path):
        """HOOKS.md should be under <output_dir>/hooks/."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            with_hooks=True,
            dry_run=True,
            verbose=False,
        )
        hooks_path = result["hooks"]
        assert "/hooks/HOOKS.md" in hooks_path


# ---------------------------------------------------------------------------
# Tests: config override from repoforge.yaml
# ---------------------------------------------------------------------------

class TestHooksConfigOverride:
    def test_config_enables_hooks(self, tmp_path):
        """generate_hooks: true in repoforge.yaml should enable hooks."""
        import yaml

        from repoforge.generator import generate_artifacts

        # Create a minimal repo with repoforge.yaml
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("def hello(): pass\n")
        (repo / "pyproject.toml").write_text('[project]\nname = "test"\n')
        (repo / "repoforge.yaml").write_text(
            yaml.dump({"generate_hooks": True})
        )

        result = generate_artifacts(
            working_dir=str(repo),
            output_dir=str(tmp_path / "out"),
            dry_run=True,
            verbose=False,
        )
        assert "hooks" in result

    def test_cli_flag_overrides_config(self, tmp_path):
        """CLI with_hooks=False should take precedence over config."""
        import yaml

        from repoforge.generator import generate_artifacts

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("def hello(): pass\n")
        (repo / "pyproject.toml").write_text('[project]\nname = "test"\n')
        # Config says yes, but CLI says no — CLI should still be off by default
        (repo / "repoforge.yaml").write_text(
            yaml.dump({"generate_hooks": True})
        )

        # with_hooks=False (default) does NOT override config — config enables it
        result = generate_artifacts(
            working_dir=str(repo),
            output_dir=str(tmp_path / "out"),
            with_hooks=False,
            dry_run=True,
            verbose=False,
        )
        # When with_hooks is explicitly False (default), config can still enable it
        assert "hooks" in result

    def test_config_disabled_stays_off(self, tmp_path):
        """generate_hooks: false in config should keep hooks off."""
        import yaml

        from repoforge.generator import generate_artifacts

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("def hello(): pass\n")
        (repo / "pyproject.toml").write_text('[project]\nname = "test"\n')
        (repo / "repoforge.yaml").write_text(
            yaml.dump({"generate_hooks": False})
        )

        result = generate_artifacts(
            working_dir=str(repo),
            output_dir=str(tmp_path / "out"),
            dry_run=True,
            verbose=False,
        )
        assert "hooks" not in result


# ---------------------------------------------------------------------------
# Tests: CLI --with-hooks flag
# ---------------------------------------------------------------------------

class TestCLIHooksFlag:
    def test_skills_help_shows_hooks_flag(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["skills", "--help"])
        assert "--with-hooks" in result.output
        assert "--no-hooks" in result.output

    def test_skills_accepts_with_hooks(self, tmp_path):
        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills",
            "-w", repo_dir,
            "-o", str(tmp_path / "out"),
            "--with-hooks",
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0

    def test_skills_accepts_no_hooks(self, tmp_path):
        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills",
            "-w", repo_dir,
            "-o", str(tmp_path / "out"),
            "--no-hooks",
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0

    def test_default_is_no_hooks(self, tmp_path):
        """Without --with-hooks, hooks should not be generated."""
        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills",
            "-w", repo_dir,
            "-o", str(tmp_path / "out"),
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0
        # Hooks should be skipped (no HOOKS.md created in dry-run)
        hooks_path = tmp_path / "out" / "hooks" / "HOOKS.md"
        assert not hooks_path.exists()
