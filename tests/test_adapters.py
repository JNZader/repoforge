"""
tests/test_adapters.py — Tests for multi-tool output adapters.

Tests cover:
- adapt_for_cursor: .mdc format, frontmatter, glob generation
- adapt_for_codex: AGENTS.md with TOC and combined sections
- adapt_for_gemini: GEMINI.md with project instructions
- adapt_for_copilot: .github/copilot-instructions.md
- resolve_targets: parsing, validation, "all" shorthand
- run_adapters: dispatcher integration
- _strip_yaml_frontmatter: YAML parsing helper
- _layer_to_globs: glob mapping helper
- _skill_name_from_path: name derivation helper
- CLI --targets flag integration
- Generator integration with targets (dry-run)
"""

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SKILL_CONTENT = """\
---
name: backend-layer
description: >
  Backend patterns for FastAPI REST endpoints.
  Trigger: When working in backend/ — adding, modifying, or debugging backend code.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Add a new endpoint

Use FastAPI router decorators.

```python
@router.get("/users")
async def get_users():
    return await UserService.list_all()
```

## When to Use

- Adding new REST endpoints
- Modifying existing API routes

## Anti-Patterns

### Don't: hardcode database URLs

Use environment variables instead.

## Quick Reference

| Task | Pattern |
|------|---------|
| New endpoint | `@router.get("/path")` |
"""

SAMPLE_MODULE_SKILL = """\
---
name: add-user-endpoint
description: >
  User management patterns for the users module.
  Trigger: When working with users, user creation, or authentication.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Create a user

```python
user = UserCreate(name="test", email="test@example.com")
result = await create_user(user)
```

## Anti-Patterns

### Don't: skip validation

Always validate input with Pydantic models.
"""

SAMPLE_AGENT_CONTENT = """\
---
name: backend-agent
description: >
  Specialized agent for backend. Handles API endpoints and services.
  Trigger: When the orchestrator needs to work in backend/.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Role

Owns the backend layer. Handles all API endpoints, services, and models.

## Capabilities

- Add and modify REST endpoints
- Manage database models
- Run backend tests
"""

SKILL_NO_FRONTMATTER = """\
## Critical Patterns

### Simple pattern

Just some content without frontmatter.
"""


@pytest.fixture
def sample_skills():
    """Dict of {relative_path: content} for skills."""
    return {
        "skills/backend/SKILL.md": SAMPLE_SKILL_CONTENT,
        "skills/backend/users/SKILL.md": SAMPLE_MODULE_SKILL,
    }


@pytest.fixture
def sample_agents():
    """Dict of {relative_path: content} for agents."""
    return {
        "agents/backend-agent/AGENT.md": SAMPLE_AGENT_CONTENT,
    }


@pytest.fixture
def sample_repo_map():
    return {
        "root": "/fake/project",
        "tech_stack": ["Python", "FastAPI"],
        "entry_points": ["backend/main.py"],
        "config_files": ["pyproject.toml"],
        "layers": {
            "backend": {
                "path": "backend",
                "modules": [
                    {
                        "path": "backend/routers/users.py",
                        "name": "users",
                        "language": "Python",
                        "exports": ["get_users", "create_user"],
                        "imports": ["fastapi"],
                        "summary_hint": "User endpoints",
                    },
                ],
            }
        },
        "stats": {"total_files": 10, "rg_available": False, "rg_version": None},
    }


# ---------------------------------------------------------------------------
# Tests: _strip_yaml_frontmatter helper
# ---------------------------------------------------------------------------

class TestStripYamlFrontmatter:
    def test_extracts_name(self):
        from repoforge.adapters import _strip_yaml_frontmatter
        fm, body = _strip_yaml_frontmatter(SAMPLE_SKILL_CONTENT)
        assert fm["name"] == "backend-layer"

    def test_extracts_description(self):
        from repoforge.adapters import _strip_yaml_frontmatter
        fm, _ = _strip_yaml_frontmatter(SAMPLE_SKILL_CONTENT)
        assert "Backend patterns" in fm["description"]

    def test_body_has_no_frontmatter(self):
        from repoforge.adapters import _strip_yaml_frontmatter
        _, body = _strip_yaml_frontmatter(SAMPLE_SKILL_CONTENT)
        assert not body.startswith("---")
        assert "## Critical Patterns" in body

    def test_handles_no_frontmatter(self):
        from repoforge.adapters import _strip_yaml_frontmatter
        fm, body = _strip_yaml_frontmatter(SKILL_NO_FRONTMATTER)
        assert fm == {}
        assert "## Critical Patterns" in body

    def test_handles_empty_string(self):
        from repoforge.adapters import _strip_yaml_frontmatter
        fm, body = _strip_yaml_frontmatter("")
        assert fm == {}
        assert body == ""


# ---------------------------------------------------------------------------
# Tests: _layer_to_globs helper
# ---------------------------------------------------------------------------

class TestLayerToGlobs:
    def test_python_stack(self):
        from repoforge.adapters import _layer_to_globs
        globs = _layer_to_globs("backend", ["Python", "FastAPI"])
        assert any("**/*.py" in g for g in globs)
        assert all("backend/" in g for g in globs)

    def test_typescript_stack(self):
        from repoforge.adapters import _layer_to_globs
        globs = _layer_to_globs("frontend", ["TypeScript", "React"])
        assert any("**/*.ts" in g for g in globs)
        assert all("frontend/" in g for g in globs)

    def test_go_stack(self):
        from repoforge.adapters import _layer_to_globs
        globs = _layer_to_globs("api", ["Go"])
        assert any("**/*.go" in g for g in globs)

    def test_main_layer_no_prefix(self):
        from repoforge.adapters import _layer_to_globs
        globs = _layer_to_globs("main", ["Python"])
        assert not any(g.startswith("main/") for g in globs)

    def test_dot_layer_no_prefix(self):
        from repoforge.adapters import _layer_to_globs
        globs = _layer_to_globs(".", ["Python"])
        assert not any(g.startswith("./") for g in globs)

    def test_fallback_no_stack(self):
        from repoforge.adapters import _layer_to_globs
        globs = _layer_to_globs("backend")
        assert len(globs) > 0  # should provide fallback globs


# ---------------------------------------------------------------------------
# Tests: _skill_name_from_path helper
# ---------------------------------------------------------------------------

class TestSkillNameFromPath:
    def test_layer_skill(self):
        from repoforge.adapters import _skill_name_from_path
        name = _skill_name_from_path("backend/SKILL.md")
        assert name == "backend"

    def test_module_skill(self):
        from repoforge.adapters import _skill_name_from_path
        name = _skill_name_from_path("backend/users/SKILL.md")
        assert name == "backend-users"

    def test_strips_skills_prefix(self):
        from repoforge.adapters import _skill_name_from_path
        name = _skill_name_from_path("skills/backend/SKILL.md")
        assert name == "backend"

    def test_agent_path(self):
        from repoforge.adapters import _skill_name_from_path
        name = _skill_name_from_path("agents/backend-agent/AGENT.md")
        assert name == "backend-agent"

    def test_fallback_empty(self):
        from repoforge.adapters import _skill_name_from_path
        name = _skill_name_from_path("SKILL.md")
        assert name == "main"


# ---------------------------------------------------------------------------
# Tests: adapt_for_cursor
# ---------------------------------------------------------------------------

class TestAdaptForCursor:
    def test_returns_mdc_files(self, sample_skills, sample_repo_map):
        from repoforge.adapters import adapt_for_cursor
        result = adapt_for_cursor(sample_skills, sample_repo_map)
        assert len(result) == 2
        assert all(p.endswith(".mdc") for p in result)

    def test_output_path_in_cursor_rules(self, sample_skills, sample_repo_map):
        from repoforge.adapters import adapt_for_cursor
        result = adapt_for_cursor(sample_skills, sample_repo_map)
        assert all(p.startswith(".cursor/rules/") for p in result)

    def test_mdc_has_description_frontmatter(self, sample_skills, sample_repo_map):
        from repoforge.adapters import adapt_for_cursor
        result = adapt_for_cursor(sample_skills, sample_repo_map)
        for content in result.values():
            assert content.startswith("---")
            assert "description:" in content

    def test_mdc_has_globs(self, sample_skills, sample_repo_map):
        from repoforge.adapters import adapt_for_cursor
        result = adapt_for_cursor(sample_skills, sample_repo_map)
        for content in result.values():
            assert "globs:" in content

    def test_mdc_has_always_apply(self, sample_skills, sample_repo_map):
        from repoforge.adapters import adapt_for_cursor
        result = adapt_for_cursor(sample_skills, sample_repo_map)
        for content in result.values():
            assert "alwaysApply: false" in content

    def test_mdc_body_preserved(self, sample_skills, sample_repo_map):
        from repoforge.adapters import adapt_for_cursor
        result = adapt_for_cursor(sample_skills, sample_repo_map)
        # At least one output should contain the skill body
        all_content = "\n".join(result.values())
        assert "## Critical Patterns" in all_content

    def test_name_from_frontmatter(self, sample_skills, sample_repo_map):
        from repoforge.adapters import adapt_for_cursor
        result = adapt_for_cursor(sample_skills, sample_repo_map)
        paths = list(result.keys())
        assert ".cursor/rules/backend-layer.mdc" in paths

    def test_globs_use_python_extensions(self, sample_skills, sample_repo_map):
        from repoforge.adapters import adapt_for_cursor
        result = adapt_for_cursor(sample_skills, sample_repo_map)
        for content in result.values():
            assert "*.py" in content

    def test_no_repo_map_fallback(self, sample_skills):
        from repoforge.adapters import adapt_for_cursor
        result = adapt_for_cursor(sample_skills)
        assert len(result) == 2  # should still work

    def test_empty_skills(self, sample_repo_map):
        from repoforge.adapters import adapt_for_cursor
        result = adapt_for_cursor({}, sample_repo_map)
        assert result == {}


# ---------------------------------------------------------------------------
# Tests: adapt_for_codex
# ---------------------------------------------------------------------------

class TestAdaptForCodex:
    def test_returns_agents_md(self, sample_skills, sample_agents):
        from repoforge.adapters import adapt_for_codex
        result = adapt_for_codex(sample_skills, sample_agents)
        assert "AGENTS.md" in result

    def test_single_file_output(self, sample_skills):
        from repoforge.adapters import adapt_for_codex
        result = adapt_for_codex(sample_skills)
        assert len(result) == 1

    def test_contains_header(self, sample_skills):
        from repoforge.adapters import adapt_for_codex
        result = adapt_for_codex(sample_skills)
        assert "# Project Instructions (AGENTS.md)" in result["AGENTS.md"]

    def test_contains_toc(self, sample_skills):
        from repoforge.adapters import adapt_for_codex
        result = adapt_for_codex(sample_skills)
        assert "## Table of Contents" in result["AGENTS.md"]

    def test_contains_skills_section(self, sample_skills):
        from repoforge.adapters import adapt_for_codex
        result = adapt_for_codex(sample_skills)
        assert "## Skills" in result["AGENTS.md"]

    def test_contains_agents_section(self, sample_skills, sample_agents):
        from repoforge.adapters import adapt_for_codex
        result = adapt_for_codex(sample_skills, sample_agents)
        assert "## Agents" in result["AGENTS.md"]

    def test_skill_content_included(self, sample_skills):
        from repoforge.adapters import adapt_for_codex
        result = adapt_for_codex(sample_skills)
        content = result["AGENTS.md"]
        assert "## Critical Patterns" in content
        assert "FastAPI router" in content or "endpoint" in content.lower()

    def test_agent_content_included(self, sample_skills, sample_agents):
        from repoforge.adapters import adapt_for_codex
        result = adapt_for_codex(sample_skills, sample_agents)
        content = result["AGENTS.md"]
        assert "backend-agent" in content

    def test_repoforge_attribution(self, sample_skills):
        from repoforge.adapters import adapt_for_codex
        result = adapt_for_codex(sample_skills)
        assert "RepoForge" in result["AGENTS.md"]

    def test_no_yaml_frontmatter_in_output(self, sample_skills):
        from repoforge.adapters import adapt_for_codex
        result = adapt_for_codex(sample_skills)
        content = result["AGENTS.md"]
        # Frontmatter should be stripped, not included in combined output
        assert "license: Apache-2.0" not in content

    def test_empty_skills(self):
        from repoforge.adapters import adapt_for_codex
        result = adapt_for_codex({})
        assert "AGENTS.md" in result

    def test_no_agents_still_works(self, sample_skills):
        from repoforge.adapters import adapt_for_codex
        result = adapt_for_codex(sample_skills, None)
        assert "## Agents" not in result["AGENTS.md"]


# ---------------------------------------------------------------------------
# Tests: adapt_for_gemini
# ---------------------------------------------------------------------------

class TestAdaptForGemini:
    def test_returns_gemini_md(self, sample_skills):
        from repoforge.adapters import adapt_for_gemini
        result = adapt_for_gemini(sample_skills)
        assert "GEMINI.md" in result

    def test_single_file_output(self, sample_skills):
        from repoforge.adapters import adapt_for_gemini
        result = adapt_for_gemini(sample_skills)
        assert len(result) == 1

    def test_contains_gemini_header(self, sample_skills):
        from repoforge.adapters import adapt_for_gemini
        result = adapt_for_gemini(sample_skills)
        assert "# Project Instructions (GEMINI.md)" in result["GEMINI.md"]

    def test_gemini_specific_context(self, sample_skills):
        from repoforge.adapters import adapt_for_gemini
        result = adapt_for_gemini(sample_skills)
        assert "Gemini CLI" in result["GEMINI.md"]

    def test_contains_toc(self, sample_skills):
        from repoforge.adapters import adapt_for_gemini
        result = adapt_for_gemini(sample_skills)
        assert "## Table of Contents" in result["GEMINI.md"]

    def test_skill_content_included(self, sample_skills):
        from repoforge.adapters import adapt_for_gemini
        result = adapt_for_gemini(sample_skills)
        assert "## Critical Patterns" in result["GEMINI.md"]

    def test_agents_included(self, sample_skills, sample_agents):
        from repoforge.adapters import adapt_for_gemini
        result = adapt_for_gemini(sample_skills, sample_agents)
        assert "## Agents" in result["GEMINI.md"]
        assert "backend-agent" in result["GEMINI.md"]

    def test_no_yaml_frontmatter_in_output(self, sample_skills):
        from repoforge.adapters import adapt_for_gemini
        result = adapt_for_gemini(sample_skills)
        assert "license: Apache-2.0" not in result["GEMINI.md"]

    def test_empty_skills(self):
        from repoforge.adapters import adapt_for_gemini
        result = adapt_for_gemini({})
        assert "GEMINI.md" in result


# ---------------------------------------------------------------------------
# Tests: adapt_for_copilot
# ---------------------------------------------------------------------------

class TestAdaptForCopilot:
    def test_returns_copilot_instructions(self, sample_skills):
        from repoforge.adapters import adapt_for_copilot
        result = adapt_for_copilot(sample_skills)
        assert ".github/copilot-instructions.md" in result

    def test_single_file_output(self, sample_skills):
        from repoforge.adapters import adapt_for_copilot
        result = adapt_for_copilot(sample_skills)
        assert len(result) == 1

    def test_contains_copilot_header(self, sample_skills):
        from repoforge.adapters import adapt_for_copilot
        result = adapt_for_copilot(sample_skills)
        content = result[".github/copilot-instructions.md"]
        assert "# Copilot Instructions" in content

    def test_skill_sections_present(self, sample_skills):
        from repoforge.adapters import adapt_for_copilot
        result = adapt_for_copilot(sample_skills)
        content = result[".github/copilot-instructions.md"]
        assert "## backend-layer" in content

    def test_skill_body_included(self, sample_skills):
        from repoforge.adapters import adapt_for_copilot
        result = adapt_for_copilot(sample_skills)
        content = result[".github/copilot-instructions.md"]
        assert "## Critical Patterns" in content

    def test_no_yaml_frontmatter(self, sample_skills):
        from repoforge.adapters import adapt_for_copilot
        result = adapt_for_copilot(sample_skills)
        content = result[".github/copilot-instructions.md"]
        assert "license: Apache-2.0" not in content

    def test_repoforge_attribution(self, sample_skills):
        from repoforge.adapters import adapt_for_copilot
        result = adapt_for_copilot(sample_skills)
        content = result[".github/copilot-instructions.md"]
        assert "RepoForge" in content

    def test_empty_skills(self):
        from repoforge.adapters import adapt_for_copilot
        result = adapt_for_copilot({})
        assert ".github/copilot-instructions.md" in result


# ---------------------------------------------------------------------------
# Tests: resolve_targets
# ---------------------------------------------------------------------------

class TestResolveTargets:
    def test_default_targets(self):
        from repoforge.adapters import resolve_targets
        result = resolve_targets("claude,opencode")
        assert result == ["claude", "opencode"]

    def test_all_shorthand(self):
        from repoforge.adapters import ALL_TARGETS, resolve_targets
        result = resolve_targets("all")
        assert result == list(ALL_TARGETS)

    def test_all_with_mixed_case(self):
        from repoforge.adapters import ALL_TARGETS, resolve_targets
        result = resolve_targets("ALL")
        assert result == list(ALL_TARGETS)

    def test_single_target(self):
        from repoforge.adapters import resolve_targets
        result = resolve_targets("cursor")
        assert result == ["cursor"]

    def test_multiple_targets(self):
        from repoforge.adapters import resolve_targets
        result = resolve_targets("claude,cursor,gemini")
        assert result == ["claude", "cursor", "gemini"]

    def test_strips_whitespace(self):
        from repoforge.adapters import resolve_targets
        result = resolve_targets(" claude , cursor , gemini ")
        assert result == ["claude", "cursor", "gemini"]

    def test_deduplicates(self):
        from repoforge.adapters import resolve_targets
        result = resolve_targets("claude,claude,cursor")
        assert result == ["claude", "cursor"]

    def test_unknown_target_raises(self):
        from repoforge.adapters import resolve_targets
        with pytest.raises(ValueError, match="Unknown target"):
            resolve_targets("claude,unknown_tool")

    def test_empty_string_raises_or_empty(self):
        from repoforge.adapters import resolve_targets
        result = resolve_targets("")
        assert result == []

    def test_case_insensitive(self):
        from repoforge.adapters import resolve_targets
        result = resolve_targets("Claude,CURSOR,Gemini")
        assert result == ["claude", "cursor", "gemini"]


# ---------------------------------------------------------------------------
# Tests: run_adapters dispatcher
# ---------------------------------------------------------------------------

class TestRunAdapters:
    def test_empty_targets(self, sample_skills):
        from repoforge.adapters import run_adapters
        result = run_adapters([], sample_skills)
        assert result == {}

    def test_cursor_target(self, sample_skills, sample_repo_map):
        from repoforge.adapters import run_adapters
        result = run_adapters(["cursor"], sample_skills, repo_map=sample_repo_map)
        assert any(p.endswith(".mdc") for p in result)

    def test_codex_target(self, sample_skills, sample_agents):
        from repoforge.adapters import run_adapters
        result = run_adapters(["codex"], sample_skills, sample_agents)
        assert "AGENTS.md" in result

    def test_gemini_target(self, sample_skills):
        from repoforge.adapters import run_adapters
        result = run_adapters(["gemini"], sample_skills)
        assert "GEMINI.md" in result

    def test_copilot_target(self, sample_skills):
        from repoforge.adapters import run_adapters
        result = run_adapters(["copilot"], sample_skills)
        assert ".github/copilot-instructions.md" in result

    def test_multiple_targets(self, sample_skills, sample_agents, sample_repo_map):
        from repoforge.adapters import run_adapters
        result = run_adapters(
            ["cursor", "codex", "gemini", "copilot"],
            sample_skills, sample_agents, sample_repo_map,
        )
        assert any(p.endswith(".mdc") for p in result)
        assert "AGENTS.md" in result
        assert "GEMINI.md" in result
        assert ".github/copilot-instructions.md" in result

    def test_claude_opencode_not_handled(self, sample_skills):
        from repoforge.adapters import run_adapters
        result = run_adapters(["claude", "opencode"], sample_skills)
        # claude and opencode are handled by generator.py, not adapters
        assert result == {}

    def test_all_adapter_targets(self, sample_skills, sample_agents, sample_repo_map):
        from repoforge.adapters import ADAPTER_TARGETS, run_adapters
        result = run_adapters(
            list(ADAPTER_TARGETS), sample_skills, sample_agents, sample_repo_map,
        )
        assert len(result) >= 4  # at least 4 outputs (2 mdc + agents + gemini + copilot)


# ---------------------------------------------------------------------------
# Tests: CLI --targets flag
# ---------------------------------------------------------------------------

class TestCLITargetsFlag:
    def test_skills_help_shows_targets(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["skills", "--help"])
        assert "--targets" in result.output

    def test_skills_accepts_targets(self, tmp_path):
        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills", "-w", repo_dir,
            "-o", str(tmp_path / "out"),
            "--targets", "claude,cursor",
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0

    def test_skills_accepts_all_targets(self, tmp_path):
        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills", "-w", repo_dir,
            "-o", str(tmp_path / "out"),
            "--targets", "all",
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0

    def test_default_no_targets_flag(self, tmp_path):
        """Without --targets, should use default claude,opencode."""
        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills", "-w", repo_dir,
            "-o", str(tmp_path / "out"),
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Tests: generator integration (dry-run)
# ---------------------------------------------------------------------------

class TestGeneratorTargetsIntegration:
    def test_default_targets_backward_compatible(self, tmp_path):
        """Without --targets, should still generate claude + opencode."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            dry_run=True,
            verbose=False,
        )
        assert "skills" in result
        assert len(result["skills"]) > 0
        # No adapter outputs since only claude+opencode (handled natively)
        assert "adapter_outputs" not in result

    def test_cursor_target_produces_adapter_outputs(self, tmp_path):
        """targets=cursor should produce adapter outputs."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            targets="claude,cursor",
            dry_run=True,
            verbose=False,
        )
        assert "adapter_targets" in result
        assert "cursor" in result["adapter_targets"]
        assert "adapter_outputs" in result
        assert any(".mdc" in p for p in result["adapter_outputs"])

    def test_all_targets(self, tmp_path):
        """targets=all should produce outputs for all adapter targets."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            targets="all",
            dry_run=True,
            verbose=False,
        )
        assert "adapter_targets" in result
        assert "cursor" in result["adapter_targets"]
        assert "codex" in result["adapter_targets"]
        assert "gemini" in result["adapter_targets"]
        assert "copilot" in result["adapter_targets"]
        outputs = result["adapter_outputs"]
        assert any(".mdc" in p for p in outputs)
        assert "AGENTS.md" in outputs
        assert "GEMINI.md" in outputs
        assert ".github/copilot-instructions.md" in outputs

    def test_codex_only_target(self, tmp_path):
        """targets=codex should still generate claude skills (primary), plus AGENTS.md."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            targets="claude,codex",
            dry_run=True,
            verbose=False,
        )
        assert "adapter_targets" in result
        assert "codex" in result["adapter_targets"]
        assert "AGENTS.md" in result["adapter_outputs"]

    def test_no_opencode_when_excluded(self, tmp_path):
        """targets=claude,cursor should NOT generate opencode mirror."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            targets="claude,cursor",
            dry_run=True,
            verbose=False,
        )
        # When opencode is not in targets, it should be skipped
        # (in dry-run no files are written anyway, but adapter_targets should not include opencode)
        assert "opencode" not in result.get("adapter_targets", [])


# ---------------------------------------------------------------------------
# Tests: config override from repoforge.yaml
# ---------------------------------------------------------------------------

class TestTargetsConfigOverride:
    def test_config_targets_used(self, tmp_path):
        """targets from repoforge.yaml should be used when CLI flag absent."""
        import yaml

        from repoforge.generator import generate_artifacts

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("def hello(): pass\n")
        (repo / "pyproject.toml").write_text('[project]\nname = "test"\n')
        (repo / "repoforge.yaml").write_text(
            yaml.dump({"targets": ["claude", "cursor", "gemini"]})
        )

        result = generate_artifacts(
            working_dir=str(repo),
            output_dir=str(tmp_path / "out"),
            dry_run=True,
            verbose=False,
        )
        assert "adapter_targets" in result
        assert "cursor" in result["adapter_targets"]
        assert "gemini" in result["adapter_targets"]

    def test_cli_targets_override_config(self, tmp_path):
        """CLI --targets should take precedence over config."""
        import yaml

        from repoforge.generator import generate_artifacts

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("def hello(): pass\n")
        (repo / "pyproject.toml").write_text('[project]\nname = "test"\n')
        (repo / "repoforge.yaml").write_text(
            yaml.dump({"targets": ["claude", "cursor", "gemini"]})
        )

        result = generate_artifacts(
            working_dir=str(repo),
            output_dir=str(tmp_path / "out"),
            targets="claude,copilot",
            dry_run=True,
            verbose=False,
        )
        assert "adapter_targets" in result
        assert "copilot" in result["adapter_targets"]
        # cursor and gemini from config should NOT be present
        assert "cursor" not in result["adapter_targets"]
        assert "gemini" not in result["adapter_targets"]
