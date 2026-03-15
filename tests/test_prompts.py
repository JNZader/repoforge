"""
tests/test_prompts.py — Tests for SKILL.md / AGENT.md prompt format.

Validates that generated prompts produce output compatible with:
  - Gentleman-Skills format (frontmatter, structure)
  - agent-teams-lite (skill-registry, delegate-only orchestrator)
"""
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_module():
    return {
        "path": "backend/routers/users.py",
        "name": "users",
        "language": "Python",
        "exports": ["get_users", "create_user", "UserRouter"],
        "imports": ["fastapi", "pydantic"],
        "summary_hint": "User management REST endpoints",
    }


@pytest.fixture
def sample_repo_map():
    return {
        "root": "/fake/project",
        "tech_stack": ["Python", "FastAPI"],
        "entry_points": ["backend/main.py"],
        "config_files": ["pyproject.toml", "docker-compose.yml"],
        "layers": {
            "backend": {
                "path": "backend",
                "modules": [
                    {
                        "path": "backend/routers/users.py",
                        "name": "users",
                        "language": "Python",
                        "exports": ["get_users", "create_user", "UserRouter"],
                        "imports": ["fastapi", "pydantic"],
                        "summary_hint": "User REST endpoints",
                    },
                    {
                        "path": "backend/models/user.py",
                        "name": "user",
                        "language": "Python",
                        "exports": ["User", "UserCreate", "UserResponse"],
                        "imports": ["pydantic", "sqlalchemy"],
                        "summary_hint": "User data models",
                    },
                ],
            }
        },
        "stats": {"total_files": 10, "rg_available": False, "rg_version": None},
    }


@pytest.fixture
def monorepo_map():
    return {
        "root": "/fake/mono",
        "tech_stack": ["Python", "FastAPI", "TypeScript", "React"],
        "entry_points": ["backend/main.py", "frontend/src/index.tsx"],
        "config_files": ["docker-compose.yml", "pyproject.toml", "package.json"],
        "layers": {
            "frontend": {
                "path": "frontend",
                "modules": [
                    {"path": "frontend/src/App.tsx", "name": "App",
                     "language": "TypeScript", "exports": ["App"],
                     "imports": ["react"], "summary_hint": "Root app component"},
                ],
            },
            "backend": {
                "path": "backend",
                "modules": [
                    {"path": "backend/main.py", "name": "main",
                     "language": "Python", "exports": ["app"],
                     "imports": ["fastapi"], "summary_hint": "FastAPI app"},
                ],
            },
        },
        "stats": {"total_files": 20, "rg_available": False, "rg_version": None},
    }


# ---------------------------------------------------------------------------
# Tests: skill_prompt format
# ---------------------------------------------------------------------------

class TestSkillPrompt:
    def test_returns_system_and_user(self, sample_module, sample_repo_map):
        from repoforge.prompts import skill_prompt
        system, user = skill_prompt(sample_module, "backend", sample_repo_map)
        assert isinstance(system, str) and len(system) > 50
        assert isinstance(user, str) and len(user) > 50

    def test_system_mentions_gentleman_skills_format(self, sample_module, sample_repo_map):
        from repoforge.prompts import skill_prompt
        system, _ = skill_prompt(sample_module, "backend", sample_repo_map)
        # Must instruct frontmatter with required fields
        assert "name:" in system
        assert "description:" in system
        assert "Trigger:" in system
        assert "license:" in system
        assert "metadata:" in system

    def test_user_contains_real_exports(self, sample_module, sample_repo_map):
        from repoforge.prompts import skill_prompt
        _, user = skill_prompt(sample_module, "backend", sample_repo_map)
        assert "get_users" in user or "UserRouter" in user or "create_user" in user

    def test_user_contains_module_path(self, sample_module, sample_repo_map):
        from repoforge.prompts import skill_prompt
        _, user = skill_prompt(sample_module, "backend", sample_repo_map)
        assert "backend/routers/users.py" in user

    def test_user_contains_tech_stack(self, sample_module, sample_repo_map):
        from repoforge.prompts import skill_prompt
        _, user = skill_prompt(sample_module, "backend", sample_repo_map)
        assert "FastAPI" in user or "Python" in user

    def test_system_requires_apache_license(self, sample_module, sample_repo_map):
        from repoforge.prompts import skill_prompt
        system, _ = skill_prompt(sample_module, "backend", sample_repo_map)
        assert "Apache-2.0" in system

    def test_system_requires_kebab_case_name(self, sample_module, sample_repo_map):
        from repoforge.prompts import skill_prompt
        system, _ = skill_prompt(sample_module, "backend", sample_repo_map)
        assert "kebab-case" in system or "kebab" in system

    def test_system_requires_anti_patterns(self, sample_module, sample_repo_map):
        from repoforge.prompts import skill_prompt
        system, _ = skill_prompt(sample_module, "backend", sample_repo_map)
        assert "Anti-Pattern" in system or "anti-pattern" in system.lower()

    def test_user_suggests_action_based_name(self, sample_module, sample_repo_map):
        from repoforge.prompts import skill_prompt
        _, user = skill_prompt(sample_module, "backend", sample_repo_map)
        # Should suggest action-verb + domain, not just module name
        assert "add-" in user or "extend-" in user or "action" in user.lower()

    def test_system_starts_with_critical_patterns(self, sample_module, sample_repo_map):
        from repoforge.prompts import skill_prompt
        system, _ = skill_prompt(sample_module, "backend", sample_repo_map)
        # New format goes straight to Critical Patterns — not verbose overview sections
        assert "## Critical Patterns" in system
        assert "## When to Use" in system
        assert "## Anti-Patterns" in system


# ---------------------------------------------------------------------------
# Tests: layer_skill_prompt format
# ---------------------------------------------------------------------------

class TestLayerSkillPrompt:
    def test_returns_tuple(self, sample_repo_map):
        from repoforge.prompts import layer_skill_prompt
        layer = sample_repo_map["layers"]["backend"]
        system, user = layer_skill_prompt("backend", layer, sample_repo_map)
        assert isinstance(system, str)
        assert isinstance(user, str)

    def test_name_must_be_layer_name_layer(self, sample_repo_map):
        from repoforge.prompts import layer_skill_prompt
        layer = sample_repo_map["layers"]["backend"]
        system, user = layer_skill_prompt("backend", layer, sample_repo_map)
        assert "backend-layer" in system or "backend-layer" in user

    def test_system_requires_adding_new_section(self, sample_repo_map):
        from repoforge.prompts import layer_skill_prompt
        layer = sample_repo_map["layers"]["backend"]
        system, _ = layer_skill_prompt("backend", layer, sample_repo_map)
        assert "Adding a New" in system

    def test_user_lists_modules(self, sample_repo_map):
        from repoforge.prompts import layer_skill_prompt
        layer = sample_repo_map["layers"]["backend"]
        _, user = layer_skill_prompt("backend", layer, sample_repo_map)
        assert "users.py" in user or "user.py" in user

    def test_multilang_note_in_user(self):
        from repoforge.prompts import layer_skill_prompt
        multilang_layer = {
            "path": "shared",
            "modules": [
                {"path": "shared/types.ts", "name": "types", "language": "TypeScript",
                 "exports": ["UserType"], "imports": [], "summary_hint": ""},
                {"path": "shared/utils.py", "name": "utils", "language": "Python",
                 "exports": ["helper"], "imports": [], "summary_hint": ""},
            ],
        }
        repo_map = {
            "tech_stack": ["Python", "TypeScript"],
            "entry_points": [],
            "config_files": [],
            "layers": {"shared": multilang_layer},
        }
        _, user = layer_skill_prompt("shared", multilang_layer, repo_map)
        assert "MULTILANGUAGE" in user or "multiple" in user.lower() or "TypeScript" in user


# ---------------------------------------------------------------------------
# Tests: agent_prompt format
# ---------------------------------------------------------------------------

class TestAgentPrompt:
    def test_returns_tuple(self, sample_repo_map):
        from repoforge.prompts import agent_prompt
        layer = sample_repo_map["layers"]["backend"]
        system, user = agent_prompt("backend", layer, sample_repo_map, ["backend"])
        assert isinstance(system, str)
        assert isinstance(user, str)

    def test_system_requires_skill_registry_read(self, sample_repo_map):
        from repoforge.prompts import agent_prompt
        layer = sample_repo_map["layers"]["backend"]
        system, _ = agent_prompt("backend", layer, sample_repo_map, ["backend"])
        assert "skill-registry" in system

    def test_system_requires_delegate_only_constraint(self, sample_repo_map):
        from repoforge.prompts import agent_prompt
        layer = sample_repo_map["layers"]["backend"]
        system, _ = agent_prompt("backend", layer, sample_repo_map, ["backend"])
        assert "ONLY modify" in system or "NEVER modify" in system

    def test_system_has_input_output_format(self, sample_repo_map):
        from repoforge.prompts import agent_prompt
        layer = sample_repo_map["layers"]["backend"]
        system, _ = agent_prompt("backend", layer, sample_repo_map, ["backend"])
        assert "## Input" in system
        assert "## Output" in system

    def test_user_sets_agent_name(self, sample_repo_map):
        from repoforge.prompts import agent_prompt
        layer = sample_repo_map["layers"]["backend"]
        _, user = agent_prompt("backend", layer, sample_repo_map, ["backend"])
        assert "backend-agent" in user

    def test_user_includes_skills_dir(self, sample_repo_map):
        from repoforge.prompts import agent_prompt
        layer = sample_repo_map["layers"]["backend"]
        _, user = agent_prompt("backend", layer, sample_repo_map, ["backend"])
        assert ".claude/skills/backend" in user

    def test_system_has_license_field(self, sample_repo_map):
        from repoforge.prompts import agent_prompt
        layer = sample_repo_map["layers"]["backend"]
        system, _ = agent_prompt("backend", layer, sample_repo_map, ["backend"])
        assert "Apache-2.0" in system


# ---------------------------------------------------------------------------
# Tests: orchestrator_prompt format
# ---------------------------------------------------------------------------

class TestOrchestratorPrompt:
    def test_returns_tuple(self, sample_repo_map):
        from repoforge.prompts import orchestrator_prompt
        system, user = orchestrator_prompt(sample_repo_map)
        assert isinstance(system, str)
        assert isinstance(user, str)

    def test_system_enforces_delegate_only(self, sample_repo_map):
        from repoforge.prompts import orchestrator_prompt
        system, _ = orchestrator_prompt(sample_repo_map)
        assert "NEVER writes code" in system or "NEVER write" in system

    def test_system_has_routing_table(self, sample_repo_map):
        from repoforge.prompts import orchestrator_prompt
        system, _ = orchestrator_prompt(sample_repo_map)
        assert "Routing Table" in system

    def test_system_requires_skill_registry(self, sample_repo_map):
        from repoforge.prompts import orchestrator_prompt
        system, _ = orchestrator_prompt(sample_repo_map)
        assert "skill-registry" in system

    def test_user_mentions_all_layer_agents(self, monorepo_map):
        from repoforge.prompts import orchestrator_prompt
        _, user = orchestrator_prompt(monorepo_map)
        assert "frontend-agent" in user
        assert "backend-agent" in user

    def test_name_must_be_orchestrator(self, sample_repo_map):
        from repoforge.prompts import orchestrator_prompt
        system, user = orchestrator_prompt(sample_repo_map)
        assert "name: orchestrator" in system or "name` must be: `orchestrator`" in user


# ---------------------------------------------------------------------------
# Tests: build_skill_registry
# ---------------------------------------------------------------------------

class TestSkillRegistry:
    def test_generates_markdown(self, tmp_path, sample_repo_map):
        from repoforge.prompts import build_skill_registry

        skills = [
            str(tmp_path / ".claude/skills/backend/SKILL.md"),
            str(tmp_path / ".claude/skills/backend/users/SKILL.md"),
        ]
        result = build_skill_registry(skills, sample_repo_map, tmp_path / ".claude", tmp_path)
        assert isinstance(result, str)
        assert "# Skill Registry" in result

    def test_contains_skills_table(self, tmp_path, sample_repo_map):
        from repoforge.prompts import build_skill_registry

        skills = [str(tmp_path / ".claude/skills/backend/SKILL.md")]
        result = build_skill_registry(skills, sample_repo_map, tmp_path / ".claude", tmp_path)
        assert "## Skills" in result
        assert "| Trigger |" in result

    def test_contains_project_context(self, tmp_path, sample_repo_map):
        from repoforge.prompts import build_skill_registry

        result = build_skill_registry([], sample_repo_map, tmp_path / ".claude", tmp_path)
        assert "Tech stack" in result
        assert "FastAPI" in result or "Python" in result

    def test_contains_conventions_table(self, tmp_path, sample_repo_map):
        from repoforge.prompts import build_skill_registry

        # Create a fake CLAUDE.md
        (tmp_path / "CLAUDE.md").write_text("# Instructions\n")
        result = build_skill_registry([], sample_repo_map, tmp_path / ".claude", tmp_path)
        assert "## Project Conventions" in result
        assert "CLAUDE.md" in result

    def test_skill_paths_are_relative(self, tmp_path, sample_repo_map):
        from repoforge.prompts import build_skill_registry

        skills = [str(tmp_path / ".claude/skills/backend/users/SKILL.md")]
        result = build_skill_registry(skills, sample_repo_map, tmp_path / ".claude", tmp_path)
        # Should not contain absolute paths
        assert str(tmp_path) not in result

    def test_layer_skill_trigger_mentions_directory(self, tmp_path, sample_repo_map):
        from repoforge.prompts import build_skill_registry

        # Layer-level skill: .claude/skills/backend/SKILL.md
        skills = [str(tmp_path / ".claude/skills/backend/SKILL.md")]
        result = build_skill_registry(skills, sample_repo_map, tmp_path / ".claude", tmp_path)
        assert "backend/" in result

    def test_module_skill_trigger_mentions_module(self, tmp_path, sample_repo_map):
        from repoforge.prompts import build_skill_registry

        # Module-level skill: .claude/skills/backend/users/SKILL.md
        skills = [str(tmp_path / ".claude/skills/backend/users/SKILL.md")]
        result = build_skill_registry(skills, sample_repo_map, tmp_path / ".claude", tmp_path)
        assert "users" in result

    def test_first_line_instruction(self, tmp_path, sample_repo_map):
        from repoforge.prompts import build_skill_registry

        result = build_skill_registry([], sample_repo_map, tmp_path / ".claude", tmp_path)
        assert "FIRST step" in result or "first" in result.lower()
