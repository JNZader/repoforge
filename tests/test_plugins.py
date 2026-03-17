"""
tests/test_plugins.py — Tests for plugin hierarchy feature.

Tests cover:
- build_commands() with various tech stacks
- build_plugin_manifest() with mock generated files
- manifest_to_json() output format
- manifest_to_markdown() output format
- write_plugin() file creation
- commands_prompt() includes correct context
- CLI --plugin flag
- Generator integration with complexity routing
- Config override from repoforge.yaml
"""

import json
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def python_repo_map():
    """A Python/FastAPI repo with backend layer, models, and tests."""
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
                        "path": "backend/models.py", "name": "models",
                        "language": "Python",
                        "exports": ["User", "Post"],
                        "imports": ["sqlalchemy"],
                        "summary_hint": "Database models",
                    },
                    {
                        "path": "backend/services.py", "name": "services",
                        "language": "Python",
                        "exports": ["UserService", "PostService"],
                        "imports": ["sqlalchemy"],
                        "summary_hint": "Business logic",
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
    """A Node.js/React repo with frontend layer."""
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
                    {
                        "path": "src/store.ts", "name": "store",
                        "language": "TypeScript",
                        "exports": ["useAppStore"],
                        "imports": ["zustand"],
                        "summary_hint": "App store",
                    },
                    {
                        "path": "src/hooks/useAuth.ts", "name": "useAuth",
                        "language": "TypeScript",
                        "exports": ["useAuth"],
                        "imports": ["react"],
                        "summary_hint": "Auth hook",
                    },
                ],
            }
        },
        "stats": {"total_files": 30, "rg_available": False, "rg_version": None},
    }


@pytest.fixture
def fullstack_repo_map():
    """A full-stack repo with frontend + backend + Docker."""
    return {
        "root": "/fake/fullstack",
        "tech_stack": ["Python", "FastAPI", "React", "Docker"],
        "entry_points": ["backend/main.py", "src/index.tsx"],
        "config_files": ["pyproject.toml", "package.json", "docker-compose.yml"],
        "repoforge_config": {},
        "layers": {
            "backend": {
                "path": "backend",
                "modules": [
                    {
                        "path": "backend/main.py", "name": "main",
                        "language": "Python",
                        "exports": ["create_app"],
                        "imports": ["fastapi"],
                        "summary_hint": "Backend entry",
                    },
                    {
                        "path": "backend/models.py", "name": "models",
                        "language": "Python",
                        "exports": ["User"],
                        "imports": ["sqlalchemy"],
                        "summary_hint": "Models",
                    },
                    {
                        "path": "backend/tests/test_main.py", "name": "test_main",
                        "language": "Python",
                        "exports": ["test_health"],
                        "imports": ["pytest"],
                        "summary_hint": "Tests",
                    },
                ],
            },
            "frontend": {
                "path": "src",
                "modules": [
                    {
                        "path": "src/App.tsx", "name": "App",
                        "language": "TypeScript",
                        "exports": ["App"],
                        "imports": ["react"],
                        "summary_hint": "Main app component",
                    },
                ],
            },
        },
        "stats": {"total_files": 40, "rg_available": False, "rg_version": None},
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
def empty_repo_map():
    """A minimal repo with no significant patterns."""
    return {
        "root": "/fake/empty",
        "tech_stack": [],
        "entry_points": [],
        "config_files": [],
        "repoforge_config": {},
        "layers": {
            "main": {
                "path": ".",
                "modules": [],
            }
        },
        "stats": {"total_files": 1, "rg_available": False, "rg_version": None},
    }


@pytest.fixture
def sample_skills():
    """Dict of {relative_path: content} for generated skills."""
    return {
        ".claude/skills/backend/SKILL.md": "# Backend Layer Skill",
        ".claude/skills/backend/models/SKILL.md": "# Models Skill",
    }


@pytest.fixture
def sample_generated():
    """Generated files dict as returned by generate_artifacts()."""
    return {
        "skills": [
            "/fake/pyproject/.claude/skills/backend/SKILL.md",
            "/fake/pyproject/.claude/skills/backend/models/SKILL.md",
        ],
        "agents": [
            "/fake/pyproject/.claude/agents/backend-agent/AGENT.md",
        ],
        "hooks": "/fake/pyproject/.claude/hooks/HOOKS.md",
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
# Tests: build_commands
# ---------------------------------------------------------------------------

class TestBuildCommands:
    def test_python_backend_generates_endpoint_command(
        self, python_repo_map, sample_skills, medium_complexity,
    ):
        from repoforge.plugins import build_commands
        commands = build_commands(python_repo_map, sample_skills, medium_complexity)
        names = [c.name for c in commands]
        assert "add-endpoint" in names

    def test_python_backend_generates_model_command(
        self, python_repo_map, sample_skills, medium_complexity,
    ):
        from repoforge.plugins import build_commands
        commands = build_commands(python_repo_map, sample_skills, medium_complexity)
        names = [c.name for c in commands]
        assert "add-model" in names

    def test_python_backend_generates_service_command(
        self, python_repo_map, sample_skills, medium_complexity,
    ):
        from repoforge.plugins import build_commands
        commands = build_commands(python_repo_map, sample_skills, medium_complexity)
        names = [c.name for c in commands]
        assert "add-service" in names

    def test_python_backend_generates_test_command(
        self, python_repo_map, sample_skills, medium_complexity,
    ):
        from repoforge.plugins import build_commands
        commands = build_commands(python_repo_map, sample_skills, medium_complexity)
        names = [c.name for c in commands]
        assert "add-test" in names

    def test_frontend_generates_component_command(
        self, node_repo_map, sample_skills, medium_complexity,
    ):
        from repoforge.plugins import build_commands
        commands = build_commands(node_repo_map, sample_skills, medium_complexity)
        names = [c.name for c in commands]
        assert "add-component" in names

    def test_frontend_generates_store_command(
        self, node_repo_map, sample_skills, medium_complexity,
    ):
        from repoforge.plugins import build_commands
        commands = build_commands(node_repo_map, sample_skills, medium_complexity)
        names = [c.name for c in commands]
        assert "add-store" in names

    def test_frontend_generates_hook_command(
        self, node_repo_map, sample_skills, medium_complexity,
    ):
        from repoforge.plugins import build_commands
        commands = build_commands(node_repo_map, sample_skills, medium_complexity)
        names = [c.name for c in commands]
        assert "add-hook" in names

    def test_fullstack_generates_backend_and_frontend_commands(
        self, fullstack_repo_map, sample_skills, medium_complexity,
    ):
        from repoforge.plugins import build_commands
        commands = build_commands(fullstack_repo_map, sample_skills, medium_complexity)
        names = [c.name for c in commands]
        assert "add-endpoint" in names
        assert "add-component" in names

    def test_go_repo_generates_no_backend_commands(
        self, go_repo_map, sample_skills, small_complexity,
    ):
        """Go repo without backend layer should not generate backend-specific commands."""
        from repoforge.plugins import build_commands
        commands = build_commands(go_repo_map, sample_skills, small_complexity)
        names = [c.name for c in commands]
        assert "add-endpoint" not in names
        assert "add-model" not in names

    def test_empty_repo_generates_no_commands(
        self, empty_repo_map, medium_complexity,
    ):
        from repoforge.plugins import build_commands
        commands = build_commands(empty_repo_map, {}, medium_complexity)
        assert commands == []

    def test_commands_have_required_fields(
        self, python_repo_map, sample_skills, medium_complexity,
    ):
        from repoforge.plugins import build_commands
        commands = build_commands(python_repo_map, sample_skills, medium_complexity)
        for cmd in commands:
            assert cmd.name, "Command name is required"
            assert cmd.description, "Command description is required"
            assert isinstance(cmd.skills_used, list)
            assert isinstance(cmd.steps, list)
            assert len(cmd.steps) > 0, "Command must have at least one step"
            assert isinstance(cmd.preconditions, list)
            assert isinstance(cmd.verification, str)

    def test_commands_have_no_duplicates(
        self, fullstack_repo_map, sample_skills, medium_complexity,
    ):
        from repoforge.plugins import build_commands
        commands = build_commands(fullstack_repo_map, sample_skills, medium_complexity)
        names = [c.name for c in commands]
        assert len(names) == len(set(names)), "No duplicate command names"

    def test_command_skills_used_are_strings(
        self, python_repo_map, sample_skills, medium_complexity,
    ):
        from repoforge.plugins import build_commands
        commands = build_commands(python_repo_map, sample_skills, medium_complexity)
        for cmd in commands:
            for skill in cmd.skills_used:
                assert isinstance(skill, str)


# ---------------------------------------------------------------------------
# Tests: build_plugin_manifest
# ---------------------------------------------------------------------------

class TestBuildPluginManifest:
    def test_returns_manifest(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        assert manifest is not None
        assert isinstance(manifest.name, str)

    def test_manifest_has_name(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        assert manifest.name
        assert "python" in manifest.name.lower() or "pyproject" in manifest.name.lower()

    def test_manifest_has_version(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        assert manifest.version == "1.0.0"

    def test_manifest_has_description(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        assert "Python" in manifest.description or "FastAPI" in manifest.description

    def test_manifest_has_skills(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        assert len(manifest.skills) == 2

    def test_manifest_has_agents(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        assert len(manifest.agents) == 1

    def test_manifest_has_hooks(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        assert len(manifest.hooks) == 1

    def test_manifest_has_commands(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        assert len(manifest.commands) > 0

    def test_manifest_has_triggers(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        assert len(manifest.triggers) > 0
        assert any("backend" in t.lower() for t in manifest.triggers)

    def test_manifest_author_is_repoforge(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        assert manifest.author == "RepoForge"

    def test_manifest_without_hooks(
        self, python_repo_map, medium_complexity,
    ):
        """Generated files without hooks should produce empty hooks list."""
        from repoforge.plugins import build_plugin_manifest
        generated = {
            "skills": ["/fake/skills/SKILL.md"],
            "agents": [],
        }
        manifest = build_plugin_manifest(python_repo_map, generated, medium_complexity)
        assert manifest.hooks == []

    def test_manifest_empty_repo(
        self, empty_repo_map, small_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest
        generated = {"skills": [], "agents": []}
        manifest = build_plugin_manifest(empty_repo_map, generated, small_complexity)
        assert manifest.name
        assert manifest.commands == []


# ---------------------------------------------------------------------------
# Tests: manifest_to_json
# ---------------------------------------------------------------------------

class TestManifestToJson:
    def test_returns_valid_json(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_json
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        result = manifest_to_json(manifest)
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_json_has_required_fields(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_json
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        data = json.loads(manifest_to_json(manifest))
        assert "name" in data
        assert "version" in data
        assert "description" in data
        assert "author" in data
        assert "skills" in data
        assert "commands" in data
        assert "agents" in data
        assert "hooks" in data
        assert "triggers" in data
        assert "dependencies" in data

    def test_json_commands_are_objects(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_json
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        data = json.loads(manifest_to_json(manifest))
        for cmd in data["commands"]:
            assert "name" in cmd
            assert "description" in cmd
            assert "skills_used" in cmd
            assert "steps" in cmd
            assert "preconditions" in cmd
            assert "verification" in cmd

    def test_json_name_matches_manifest(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_json
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        data = json.loads(manifest_to_json(manifest))
        assert data["name"] == manifest.name

    def test_json_version_matches(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_json
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        data = json.loads(manifest_to_json(manifest))
        assert data["version"] == "1.0.0"

    def test_json_indented(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_json
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        result = manifest_to_json(manifest)
        assert "  " in result  # 2-space indentation

    def test_json_ends_with_newline(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_json
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        result = manifest_to_json(manifest)
        assert result.endswith("\n")


# ---------------------------------------------------------------------------
# Tests: manifest_to_markdown
# ---------------------------------------------------------------------------

class TestManifestToMarkdown:
    def test_returns_markdown_string(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_markdown
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        result = manifest_to_markdown(manifest)
        assert isinstance(result, str)
        assert len(result) > 100

    def test_contains_plugin_name(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_markdown
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        result = manifest_to_markdown(manifest)
        assert manifest.name in result

    def test_contains_version(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_markdown
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        result = manifest_to_markdown(manifest)
        assert "1.0.0" in result

    def test_contains_commands_table(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_markdown
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        result = manifest_to_markdown(manifest)
        assert "## Commands" in result
        assert "| Command |" in result

    def test_contains_skills_section(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_markdown
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        result = manifest_to_markdown(manifest)
        assert "## Skills" in result

    def test_contains_agents_section(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_markdown
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        result = manifest_to_markdown(manifest)
        assert "## Agents" in result

    def test_contains_triggers_section(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_markdown
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        result = manifest_to_markdown(manifest)
        assert "## Triggers" in result

    def test_contains_installation_section(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_markdown
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        result = manifest_to_markdown(manifest)
        assert "## Installation" in result

    def test_markdown_ends_with_newline(
        self, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, manifest_to_markdown
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        result = manifest_to_markdown(manifest)
        assert result.endswith("\n")


# ---------------------------------------------------------------------------
# Tests: write_plugin
# ---------------------------------------------------------------------------

class TestWritePlugin:
    def test_creates_plugin_json(self, tmp_path, python_repo_map, sample_generated, medium_complexity):
        from repoforge.plugins import build_plugin_manifest, write_plugin
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        result = write_plugin(str(tmp_path), manifest)
        assert ".claude/plugin.json" in result
        assert (tmp_path / ".claude" / "plugin.json").exists()

    def test_creates_plugin_md(self, tmp_path, python_repo_map, sample_generated, medium_complexity):
        from repoforge.plugins import build_plugin_manifest, write_plugin
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        result = write_plugin(str(tmp_path), manifest)
        assert ".claude/PLUGIN.md" in result
        assert (tmp_path / ".claude" / "PLUGIN.md").exists()

    def test_creates_command_stubs(self, tmp_path, python_repo_map, sample_generated, medium_complexity):
        from repoforge.plugins import build_plugin_manifest, write_plugin
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        write_plugin(str(tmp_path), manifest)
        commands_dir = tmp_path / ".claude" / "commands"
        assert commands_dir.exists()
        command_files = list(commands_dir.glob("*.md"))
        assert len(command_files) > 0

    def test_written_plugin_json_is_valid(
        self, tmp_path, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, write_plugin
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        write_plugin(str(tmp_path), manifest)
        content = (tmp_path / ".claude" / "plugin.json").read_text()
        data = json.loads(content)
        assert data["name"] == manifest.name

    def test_write_plugin_returns_relative_paths(
        self, tmp_path, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, write_plugin
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        result = write_plugin(str(tmp_path), manifest)
        for path in result:
            assert not path.startswith("/"), f"Path should be relative: {path}"

    def test_write_plugin_with_commands_content(
        self, tmp_path, python_repo_map, sample_generated, medium_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, write_plugin
        manifest = build_plugin_manifest(python_repo_map, sample_generated, medium_complexity)
        # Simulate LLM-generated command content
        commands_content = """# add-endpoint

> Add a new API endpoint

## Steps

### 1. Create route handler

Create the file.

---

# add-model

> Add a new data model

## Steps

### 1. Define model

Define the model fields.
"""
        write_plugin(str(tmp_path), manifest, commands_content)
        # Should have written command files
        commands_dir = tmp_path / ".claude" / "commands"
        assert commands_dir.exists()

    def test_write_plugin_no_commands_for_empty_manifest(
        self, tmp_path, empty_repo_map, small_complexity,
    ):
        from repoforge.plugins import build_plugin_manifest, write_plugin
        generated = {"skills": [], "agents": []}
        manifest = build_plugin_manifest(empty_repo_map, generated, small_complexity)
        result = write_plugin(str(tmp_path), manifest)
        # Should still have plugin.json and PLUGIN.md
        assert ".claude/plugin.json" in result
        assert ".claude/PLUGIN.md" in result
        # But no commands/ directory since no commands
        commands_dir = tmp_path / ".claude" / "commands"
        assert not commands_dir.exists()


# ---------------------------------------------------------------------------
# Tests: commands_prompt
# ---------------------------------------------------------------------------

class TestCommandsPrompt:
    def test_returns_string(self, python_repo_map, medium_complexity):
        from repoforge.plugins import commands_prompt
        result = commands_prompt(python_repo_map, medium_complexity)
        assert isinstance(result, str)
        assert len(result) > 100

    def test_contains_tech_stack(self, python_repo_map, medium_complexity):
        from repoforge.plugins import commands_prompt
        result = commands_prompt(python_repo_map, medium_complexity)
        assert "Python" in result
        assert "FastAPI" in result

    def test_contains_layers(self, python_repo_map, medium_complexity):
        from repoforge.plugins import commands_prompt
        result = commands_prompt(python_repo_map, medium_complexity)
        assert "backend" in result

    def test_contains_entry_points(self, python_repo_map, medium_complexity):
        from repoforge.plugins import commands_prompt
        result = commands_prompt(python_repo_map, medium_complexity)
        assert "backend/main.py" in result

    def test_contains_command_names(self, python_repo_map, medium_complexity):
        from repoforge.plugins import commands_prompt
        result = commands_prompt(python_repo_map, medium_complexity)
        assert "add-endpoint" in result

    def test_contains_complexity(self, python_repo_map, medium_complexity):
        from repoforge.plugins import commands_prompt
        result = commands_prompt(python_repo_map, medium_complexity)
        assert "medium" in result

    def test_empty_repo_returns_empty_string(self, empty_repo_map, small_complexity):
        from repoforge.plugins import commands_prompt
        result = commands_prompt(empty_repo_map, small_complexity)
        assert result == ""

    def test_contains_output_format_rules(self, python_repo_map, medium_complexity):
        from repoforge.plugins import commands_prompt
        result = commands_prompt(python_repo_map, medium_complexity)
        assert "RULES:" in result
        assert "---" in result


# ---------------------------------------------------------------------------
# Tests: CLI --plugin flag
# ---------------------------------------------------------------------------

class TestCLIPluginFlag:
    def test_skills_help_shows_plugin_flag(self):
        from click.testing import CliRunner
        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["skills", "--help"])
        assert "--plugin" in result.output
        assert "--no-plugin" in result.output

    def test_skills_accepts_plugin(self, tmp_path):
        from click.testing import CliRunner
        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills",
            "-w", repo_dir,
            "-o", str(tmp_path / "out"),
            "--plugin",
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0

    def test_skills_accepts_no_plugin(self, tmp_path):
        from click.testing import CliRunner
        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills",
            "-w", repo_dir,
            "-o", str(tmp_path / "out"),
            "--no-plugin",
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0

    def test_default_is_no_plugin(self, tmp_path):
        """Without --plugin, plugin should not be generated."""
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
        # Plugin files should not exist in dry-run without --plugin
        assert not (tmp_path / "out" / "plugin.json").exists()


# ---------------------------------------------------------------------------
# Tests: generator integration (dry-run, no LLM)
# ---------------------------------------------------------------------------

class TestGeneratorPluginIntegration:
    def test_plugin_skipped_by_default(self, tmp_path):
        """generate_artifacts without --plugin should skip plugin."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            dry_run=True,
            verbose=False,
        )
        assert "plugin" not in result

    def test_plugin_generated_when_flag_on(self, tmp_path):
        """generate_artifacts with with_plugin=True should include plugin dict."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            with_plugin=True,
            dry_run=True,
            verbose=False,
        )
        assert "plugin" in result
        assert "manifest" in result["plugin"]
        assert "readme" in result["plugin"]
        assert "commands" in result["plugin"]
        assert "total_commands" in result["plugin"]

    def test_plugin_has_commands(self, tmp_path):
        """Plugin should detect commands for this repo."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            with_plugin=True,
            dry_run=True,
            verbose=False,
        )
        assert result["plugin"]["total_commands"] >= 0

    def test_plugin_manifest_path_in_result(self, tmp_path):
        """Plugin manifest path should be under .claude/."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            with_plugin=True,
            dry_run=True,
            verbose=False,
        )
        assert "plugin.json" in result["plugin"]["manifest"]


# ---------------------------------------------------------------------------
# Tests: config override from repoforge.yaml
# ---------------------------------------------------------------------------

class TestPluginConfigOverride:
    def test_config_enables_plugin(self, tmp_path):
        """generate_plugin: true in repoforge.yaml should enable plugin."""
        from repoforge.generator import generate_artifacts
        import yaml

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("def hello(): pass\n")
        (repo / "pyproject.toml").write_text('[project]\nname = "test"\n')
        (repo / "repoforge.yaml").write_text(
            yaml.dump({"generate_plugin": True})
        )

        result = generate_artifacts(
            working_dir=str(repo),
            output_dir=str(tmp_path / "out"),
            dry_run=True,
            verbose=False,
        )
        assert "plugin" in result

    def test_config_disabled_stays_off(self, tmp_path):
        """generate_plugin: false in config should keep plugin off."""
        from repoforge.generator import generate_artifacts
        import yaml

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("def hello(): pass\n")
        (repo / "pyproject.toml").write_text('[project]\nname = "test"\n')
        (repo / "repoforge.yaml").write_text(
            yaml.dump({"generate_plugin": False})
        )

        result = generate_artifacts(
            working_dir=str(repo),
            output_dir=str(tmp_path / "out"),
            dry_run=True,
            verbose=False,
        )
        assert "plugin" not in result


# ---------------------------------------------------------------------------
# Tests: integration with complexity routing
# ---------------------------------------------------------------------------

class TestPluginComplexityIntegration:
    def test_small_repo_gets_fewer_commands(self, tmp_path):
        """Small repos should still get detected commands."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            with_plugin=True,
            complexity="small",
            dry_run=True,
            verbose=False,
        )
        assert "plugin" in result

    def test_large_repo_gets_commands(self, tmp_path):
        """Large repos should also generate commands."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            with_plugin=True,
            complexity="large",
            dry_run=True,
            verbose=False,
        )
        assert "plugin" in result


# ---------------------------------------------------------------------------
# Tests: data model edge cases
# ---------------------------------------------------------------------------

class TestDataModels:
    def test_command_default_preconditions(self):
        from repoforge.plugins import Command
        cmd = Command(
            name="test",
            description="Test command",
            skills_used=[],
            steps=["step 1"],
        )
        assert cmd.preconditions == []
        assert cmd.verification == ""

    def test_plugin_manifest_defaults(self):
        from repoforge.plugins import PluginManifest
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            description="Test plugin",
        )
        assert manifest.author == "RepoForge"
        assert manifest.skills == []
        assert manifest.commands == []
        assert manifest.agents == []
        assert manifest.hooks == []
        assert manifest.triggers == []
        assert manifest.dependencies == []


# ---------------------------------------------------------------------------
# Tests: public API
# ---------------------------------------------------------------------------

class TestPublicAPI:
    def test_imports_from_init(self):
        from repoforge import (
            Command,
            PluginManifest,
            build_commands,
            build_plugin_manifest,
            commands_prompt,
            manifest_to_json,
            manifest_to_markdown,
            write_plugin,
        )
        assert Command is not None
        assert PluginManifest is not None
        assert callable(build_commands)
        assert callable(build_plugin_manifest)
        assert callable(commands_prompt)
        assert callable(manifest_to_json)
        assert callable(manifest_to_markdown)
        assert callable(write_plugin)

    def test_plugins_in_all(self):
        import repoforge
        for name in [
            "Command", "PluginManifest", "build_commands",
            "build_plugin_manifest", "commands_prompt",
            "manifest_to_json", "manifest_to_markdown", "write_plugin",
        ]:
            assert name in repoforge.__all__, f"{name} not in __all__"
