"""
tests/test_complexity.py - Tests for complexity-based routing.

Tests cover:
- classify_complexity() with mock RepoMaps of various sizes
- Routing parameters correct for each size
- Override behavior (force small/medium/large)
- Integration with generator (dry-run, no LLM)
- Integration with prompts (prompt_detail parameter)
- Integration with docs (chapter capping)
"""

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def small_repo_map():
    """A small repo: 5 files, 1 layer, 2 modules."""
    return {
        "root": "/fake/small",
        "tech_stack": ["Python", "FastAPI"],
        "entry_points": ["main.py"],
        "config_files": ["pyproject.toml"],
        "repoforge_config": {},
        "layers": {
            "main": {
                "path": ".",
                "modules": [
                    {
                        "path": "main.py", "name": "main",
                        "language": "Python",
                        "exports": ["create_app", "startup"],
                        "imports": ["fastapi"],
                        "summary_hint": "App entry point",
                    },
                    {
                        "path": "routes.py", "name": "routes",
                        "language": "Python",
                        "exports": ["get_users", "create_user"],
                        "imports": ["fastapi", "pydantic"],
                        "summary_hint": "API routes",
                    },
                ],
            }
        },
        "stats": {
            "total_files": 5,
            "by_extension": {".py": 5},
            "rg_available": False,
            "rg_version": None,
        },
    }


@pytest.fixture
def medium_repo_map():
    """A medium repo: 50 files, 3 layers."""
    modules_be = [
        {
            "path": f"backend/mod{i}.py", "name": f"mod{i}",
            "language": "Python",
            "exports": [f"func_{i}a", f"func_{i}b", f"Class{i}"],
            "imports": ["fastapi"],
            "summary_hint": f"Module {i}",
        }
        for i in range(10)
    ]
    modules_fe = [
        {
            "path": f"frontend/comp{i}.tsx", "name": f"comp{i}",
            "language": "TypeScript",
            "exports": [f"Component{i}"],
            "imports": ["react"],
            "summary_hint": f"Component {i}",
        }
        for i in range(5)
    ]
    return {
        "root": "/fake/medium",
        "tech_stack": ["Python", "FastAPI", "React", "TypeScript"],
        "entry_points": ["backend/main.py"],
        "config_files": ["pyproject.toml", "package.json"],
        "repoforge_config": {},
        "layers": {
            "backend": {"path": "backend", "modules": modules_be},
            "frontend": {"path": "frontend", "modules": modules_fe},
            "shared": {"path": "shared", "modules": []},
        },
        "stats": {
            "total_files": 50,
            "by_extension": {".py": 30, ".tsx": 15, ".ts": 5},
            "rg_available": False,
            "rg_version": None,
        },
    }


@pytest.fixture
def large_repo_map():
    """A large repo: 500 files, 8 layers."""
    def make_modules(prefix, count, lang):
        return [
            {
                "path": f"{prefix}/file{i}.py" if lang == "Python" else f"{prefix}/file{i}.ts",
                "name": f"file{i}",
                "language": lang,
                "exports": [f"export_{i}_{j}" for j in range(5)],
                "imports": ["some_lib"],
                "summary_hint": f"File {i} in {prefix}",
            }
            for i in range(count)
        ]

    return {
        "root": "/fake/large",
        "tech_stack": ["Python", "FastAPI", "React", "TypeScript", "Docker", "Redis"],
        "entry_points": ["backend/main.py", "frontend/src/index.tsx"],
        "config_files": ["pyproject.toml", "package.json", "docker-compose.yml"],
        "repoforge_config": {},
        "layers": {
            "backend": {"path": "backend", "modules": make_modules("backend", 30, "Python")},
            "frontend": {"path": "frontend", "modules": make_modules("frontend", 20, "TypeScript")},
            "shared": {"path": "shared", "modules": make_modules("shared", 10, "TypeScript")},
            "workers": {"path": "workers", "modules": make_modules("workers", 15, "Python")},
            "infra": {"path": "infra", "modules": make_modules("infra", 5, "Python")},
            "mobile": {"path": "mobile", "modules": make_modules("mobile", 10, "TypeScript")},
        },
        "stats": {
            "total_files": 500,
            "by_extension": {".py": 250, ".ts": 150, ".tsx": 100},
            "rg_available": False,
            "rg_version": None,
        },
    }


# ---------------------------------------------------------------------------
# Tests: classify_complexity
# ---------------------------------------------------------------------------

class TestClassifyComplexity:
    def test_small_repo(self, small_repo_map):
        from repoforge.scanner import classify_complexity
        cx = classify_complexity(small_repo_map)
        assert cx["size"] == "small"

    def test_medium_repo(self, medium_repo_map):
        from repoforge.scanner import classify_complexity
        cx = classify_complexity(medium_repo_map)
        assert cx["size"] == "medium"

    def test_large_repo(self, large_repo_map):
        from repoforge.scanner import classify_complexity
        cx = classify_complexity(large_repo_map)
        assert cx["size"] == "large"

    def test_returns_all_required_keys(self, small_repo_map):
        from repoforge.scanner import classify_complexity
        cx = classify_complexity(small_repo_map)
        required_keys = {
            "size", "total_files", "num_layers", "total_modules",
            "max_module_skills_per_layer", "min_exports_for_skill",
            "prompt_detail", "generate_orchestrator", "generate_layer_agents",
            "max_files_per_layer", "max_chapters", "include_monorepo_hierarchy",
        }
        assert required_keys.issubset(cx.keys())

    def test_small_routing_parameters(self, small_repo_map):
        from repoforge.scanner import classify_complexity
        cx = classify_complexity(small_repo_map)
        assert cx["max_module_skills_per_layer"] == 10
        assert cx["min_exports_for_skill"] == 1
        assert cx["prompt_detail"] == "detailed"
        assert cx["generate_orchestrator"] is False
        assert cx["generate_layer_agents"] is False
        assert cx["max_files_per_layer"] == 200
        assert cx["max_chapters"] == 5
        assert cx["include_monorepo_hierarchy"] is False

    def test_medium_routing_parameters(self, medium_repo_map):
        from repoforge.scanner import classify_complexity
        cx = classify_complexity(medium_repo_map)
        assert cx["max_module_skills_per_layer"] == 5
        assert cx["min_exports_for_skill"] == 2
        assert cx["prompt_detail"] == "standard"
        assert cx["generate_orchestrator"] is True
        assert cx["generate_layer_agents"] is True
        assert cx["max_files_per_layer"] == 150
        assert cx["max_chapters"] == 7
        assert cx["include_monorepo_hierarchy"] is False

    def test_large_routing_parameters(self, large_repo_map):
        from repoforge.scanner import classify_complexity
        cx = classify_complexity(large_repo_map)
        assert cx["max_module_skills_per_layer"] == 3
        assert cx["min_exports_for_skill"] == 3
        assert cx["prompt_detail"] == "concise"
        assert cx["generate_orchestrator"] is True
        assert cx["generate_layer_agents"] is True
        assert cx["max_files_per_layer"] == 100
        assert cx["max_chapters"] == 9
        assert cx["include_monorepo_hierarchy"] is True


class TestComplexityOverride:
    def test_force_small(self, large_repo_map):
        from repoforge.scanner import classify_complexity
        cx = classify_complexity(large_repo_map, override="small")
        assert cx["size"] == "small"
        assert cx["total_files"] == 500  # stats are still real

    def test_force_large(self, small_repo_map):
        from repoforge.scanner import classify_complexity
        cx = classify_complexity(small_repo_map, override="large")
        assert cx["size"] == "large"
        assert cx["total_files"] == 5

    def test_force_medium(self, small_repo_map):
        from repoforge.scanner import classify_complexity
        cx = classify_complexity(small_repo_map, override="medium")
        assert cx["size"] == "medium"

    def test_auto_default(self, small_repo_map):
        from repoforge.scanner import classify_complexity
        cx = classify_complexity(small_repo_map, override="auto")
        assert cx["size"] == "small"

    def test_invalid_override_falls_through(self, medium_repo_map):
        from repoforge.scanner import classify_complexity
        cx = classify_complexity(medium_repo_map, override="invalid")
        # "invalid" is not in ("small", "medium", "large"), so auto-detect
        assert cx["size"] == "medium"


class TestComplexityEdgeCases:
    def test_empty_repo(self):
        from repoforge.scanner import classify_complexity
        repo_map = {
            "layers": {},
            "stats": {"total_files": 0},
        }
        cx = classify_complexity(repo_map)
        assert cx["size"] == "small"
        assert cx["total_modules"] == 0
        assert cx["num_layers"] == 0

    def test_boundary_small_to_medium(self):
        """20 files + 2 layers = still small; 21 files pushes to medium."""
        from repoforge.scanner import classify_complexity
        # Exactly at boundary: small
        small = {
            "layers": {"a": {"modules": list(range(10))}, "b": {"modules": list(range(5))}},
            "stats": {"total_files": 20},
        }
        assert classify_complexity(small)["size"] == "small"

        # Just over boundary: medium
        medium = {
            "layers": {"a": {"modules": list(range(10))}, "b": {"modules": list(range(6))}},
            "stats": {"total_files": 21},
        }
        assert classify_complexity(medium)["size"] == "medium"

    def test_boundary_medium_to_large(self):
        """200 files + 5 layers = medium; 201 files pushes to large."""
        from repoforge.scanner import classify_complexity
        medium = {
            "layers": {f"l{i}": {"modules": []} for i in range(5)},
            "stats": {"total_files": 200},
        }
        assert classify_complexity(medium)["size"] == "medium"

        large = {
            "layers": {f"l{i}": {"modules": []} for i in range(5)},
            "stats": {"total_files": 201},
        }
        assert classify_complexity(large)["size"] == "large"

    def test_many_layers_triggers_large(self):
        """6 layers even with few files → large (layers > 5)."""
        from repoforge.scanner import classify_complexity
        repo_map = {
            "layers": {f"l{i}": {"modules": []} for i in range(6)},
            "stats": {"total_files": 30},
        }
        assert classify_complexity(repo_map)["size"] == "large"


# ---------------------------------------------------------------------------
# Tests: prompt_detail integration
# ---------------------------------------------------------------------------

class TestPromptDetailIntegration:
    def test_skill_prompt_default_is_standard(self):
        """skill_prompt() with no prompt_detail is backward compatible."""
        from repoforge.prompts import skill_prompt
        module = {
            "path": "app.py", "name": "app", "language": "Python",
            "exports": ["main"], "imports": ["click"],
            "summary_hint": "CLI entry",
        }
        repo_map = {
            "tech_stack": ["Python"],
            "entry_points": [],
            "config_files": [],
            "layers": {"main": {"path": ".", "modules": [module]}},
        }
        system, user = skill_prompt(module, "main", repo_map)
        # Default: no detail instructions appended
        assert "Detail level" not in user

    def test_skill_prompt_detailed(self):
        from repoforge.prompts import skill_prompt
        module = {
            "path": "app.py", "name": "app", "language": "Python",
            "exports": ["main"], "imports": ["click"],
            "summary_hint": "CLI entry",
        }
        repo_map = {
            "tech_stack": ["Python"],
            "entry_points": [],
            "config_files": [],
            "layers": {"main": {"path": ".", "modules": [module]}},
        }
        system, user = skill_prompt(module, "main", repo_map, prompt_detail="detailed")
        assert "DETAILED" in user
        assert "3+ Critical Patterns" in user

    def test_skill_prompt_concise(self):
        from repoforge.prompts import skill_prompt
        module = {
            "path": "app.py", "name": "app", "language": "Python",
            "exports": ["main"], "imports": ["click"],
            "summary_hint": "CLI entry",
        }
        repo_map = {
            "tech_stack": ["Python"],
            "entry_points": [],
            "config_files": [],
            "layers": {"main": {"path": ".", "modules": [module]}},
        }
        system, user = skill_prompt(module, "main", repo_map, prompt_detail="concise")
        assert "CONCISE" in user
        assert "80 lines" in user

    def test_layer_skill_prompt_detailed(self):
        from repoforge.prompts import layer_skill_prompt
        layer = {
            "path": "backend",
            "modules": [
                {"path": "backend/main.py", "name": "main", "language": "Python",
                 "exports": ["app"], "imports": ["fastapi"], "summary_hint": "App"}
            ],
        }
        repo_map = {
            "tech_stack": ["Python"],
            "entry_points": [],
            "config_files": [],
            "layers": {"backend": layer},
        }
        _, user = layer_skill_prompt("backend", layer, repo_map, prompt_detail="detailed")
        assert "DETAILED" in user

    def test_layer_skill_prompt_concise(self):
        from repoforge.prompts import layer_skill_prompt
        layer = {
            "path": "backend",
            "modules": [
                {"path": "backend/main.py", "name": "main", "language": "Python",
                 "exports": ["app"], "imports": ["fastapi"], "summary_hint": "App"}
            ],
        }
        repo_map = {
            "tech_stack": ["Python"],
            "entry_points": [],
            "config_files": [],
            "layers": {"backend": layer},
        }
        _, user = layer_skill_prompt("backend", layer, repo_map, prompt_detail="concise")
        assert "CONCISE" in user


# ---------------------------------------------------------------------------
# Tests: generator integration (dry-run, no LLM)
# ---------------------------------------------------------------------------

class TestGeneratorIntegration:
    def test_dry_run_includes_complexity(self, tmp_path):
        """generate_artifacts in dry-run mode includes complexity in result."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            dry_run=True,
            verbose=False,
        )
        assert "complexity" in result
        assert result["complexity"]["size"] in ("small", "medium", "large")

    def test_force_small_skips_agents(self, tmp_path):
        """Small complexity should skip orchestrator and layer agents."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            complexity="small",
            dry_run=True,
            verbose=False,
        )
        assert result["complexity"]["size"] == "small"
        assert result["complexity"]["generate_orchestrator"] is False
        assert result["complexity"]["generate_layer_agents"] is False
        # No agents should be generated in dry-run for small
        assert len(result["agents"]) == 0

    def test_force_large_generates_agents(self, tmp_path):
        """Large complexity should generate orchestrator and layer agents."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            complexity="large",
            dry_run=True,
            verbose=False,
        )
        assert result["complexity"]["size"] == "large"
        assert result["complexity"]["generate_orchestrator"] is True
        assert len(result["agents"]) >= 1  # at least orchestrator


# ---------------------------------------------------------------------------
# Tests: docs integration
# ---------------------------------------------------------------------------

class TestDocsIntegration:
    def test_docs_dry_run_with_complexity(self, tmp_path):
        """generate_docs respects complexity parameter."""
        from repoforge.docs_generator import generate_docs
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_docs(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "docs"),
            language="English",
            complexity="small",
            dry_run=True,
            verbose=False,
        )
        assert result.get("dry_run") is True
        # Small repo should have at most 5 chapters
        assert len(result["chapters"]) <= 5

    def test_docs_large_gets_more_chapters(self, tmp_path):
        """Large complexity allows more chapters."""
        from repoforge.docs_generator import generate_docs
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_docs(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "docs"),
            language="English",
            complexity="large",
            dry_run=True,
            verbose=False,
        )
        assert result.get("dry_run") is True
        # Large allows up to 9 chapters
        assert len(result["chapters"]) <= 9


# ---------------------------------------------------------------------------
# Tests: CLI --complexity option
# ---------------------------------------------------------------------------

class TestCLIComplexity:
    def test_skills_help_shows_complexity(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["skills", "--help"])
        assert "--complexity" in result.output
        assert "auto" in result.output

    def test_docs_help_shows_complexity(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["docs", "--help"])
        assert "--complexity" in result.output
        assert "auto" in result.output

    def test_skills_accepts_complexity_flag(self, tmp_path):
        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills",
            "-w", repo_dir,
            "-o", str(tmp_path / "out"),
            "--complexity", "small",
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0

    def test_docs_accepts_complexity_flag(self, tmp_path):
        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "docs",
            "-w", repo_dir,
            "-o", str(tmp_path / "docs"),
            "--complexity", "large",
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0

    def test_invalid_complexity_rejected(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills",
            "--complexity", "huge",
            "--dry-run", "-q",
        ])
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid choice" in result.output.lower()
