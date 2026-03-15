"""
tests/test_docs.py - Tests for documentation generation pipeline.

Tests cover:
- docs_prompts: chapter selection, prompt content
- docsify: file generation, sidebar format, HTML validity
- docs_generator: dry-run, project name inference
"""

import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_repo_map():
    """Minimal repo map from scanner — no LLM needed."""
    return {
        "root": "/fake/project",
        "tech_stack": ["Python", "FastAPI"],
        "entry_points": ["main.py"],
        "config_files": ["pyproject.toml"],
        "layers": {
            "backend": {
                "path": "backend",
                "modules": [
                    {
                        "path": "backend/main.py",
                        "name": "main",
                        "language": "Python",
                        "exports": ["create_app", "startup"],
                        "imports": ["fastapi", "pydantic"],
                        "summary_hint": "Application entry point",
                    },
                    {
                        "path": "backend/routes/users.py",
                        "name": "users",
                        "language": "Python",
                        "exports": ["get_users", "create_user", "UserRouter"],
                        "imports": ["fastapi", "pydantic"],
                        "summary_hint": "User management endpoints",
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
def monorepo_map():
    """Monorepo with frontend + backend layers."""
    return {
        "root": "/fake/monorepo",
        "tech_stack": ["Python", "FastAPI", "Node.js", "React", "TypeScript", "Docker"],
        "entry_points": ["backend/main.py", "frontend/src/index.ts"],
        "config_files": ["docker-compose.yml", "pyproject.toml", "package.json"],
        "layers": {
            "frontend": {
                "path": "frontend",
                "modules": [
                    {
                        "path": "frontend/src/App.tsx",
                        "name": "App",
                        "language": "TypeScript",
                        "exports": ["App", "AppProps"],
                        "imports": ["react", "zustand"],
                        "summary_hint": "Root application component",
                    },
                    {
                        "path": "frontend/src/api/users.ts",
                        "name": "users",
                        "language": "TypeScript",
                        "exports": ["getUsers", "createUser", "UserSchema"],
                        "imports": ["zod", "axios"],
                        "summary_hint": "User API client",
                    },
                ],
            },
            "backend": {
                "path": "backend",
                "modules": [
                    {
                        "path": "backend/main.py",
                        "name": "main",
                        "language": "Python",
                        "exports": ["create_app"],
                        "imports": ["fastapi"],
                        "summary_hint": "FastAPI app factory",
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
            },
        },
        "stats": {
            "total_files": 12,
            "by_extension": {".py": 6, ".ts": 4, ".tsx": 2},
            "rg_available": False,
            "rg_version": None,
        },
    }


# ---------------------------------------------------------------------------
# Tests: docs_prompts
# ---------------------------------------------------------------------------

class TestDocsPrompts:
    def test_get_chapter_prompts_returns_list(self, minimal_repo_map):
        from repoforge.docs_prompts import get_chapter_prompts
        chapters = get_chapter_prompts(minimal_repo_map, "English", "My Project")
        assert isinstance(chapters, list)
        assert len(chapters) >= 5  # at minimum: index, overview, quickstart, architecture, core, devguide

    def test_each_chapter_has_required_keys(self, minimal_repo_map):
        from repoforge.docs_prompts import get_chapter_prompts
        chapters = get_chapter_prompts(minimal_repo_map, "English", "My Project")
        for ch in chapters:
            assert "file" in ch
            assert "title" in ch
            assert "description" in ch
            assert "system" in ch
            assert "user" in ch

    def test_index_always_included(self, minimal_repo_map):
        from repoforge.docs_prompts import get_chapter_prompts
        chapters = get_chapter_prompts(minimal_repo_map, "English", "My Project")
        files = [c["file"] for c in chapters]
        assert "index.md" in files

    def test_required_chapters_always_included(self, minimal_repo_map):
        from repoforge.docs_prompts import get_chapter_prompts
        chapters = get_chapter_prompts(minimal_repo_map, "English", "My Project")
        files = [c["file"] for c in chapters]
        # These are in UNIVERSAL_CHAPTERS — always present regardless of project type
        for required in ["index.md", "01-overview.md", "02-quickstart.md",
                         "03-architecture.md", "07-dev-guide.md"]:
            assert required in files, f"{required} missing from chapters"
        # At least one type-specific chapter must exist (beyond the universal ones)
        universal = {"index.md","01-overview.md","02-quickstart.md","03-architecture.md","07-dev-guide.md"}
        specific = [f for f in files if f not in universal]
        assert len(specific) >= 2, f"Expected type-specific chapters, got: {specific}"

    def test_language_injected_in_system_prompt(self, minimal_repo_map):
        from repoforge.docs_prompts import get_chapter_prompts
        chapters = get_chapter_prompts(minimal_repo_map, "Spanish", "Mi Proyecto")
        for ch in chapters:
            assert "Spanish" in ch["system"]

    def test_tech_stack_in_user_prompt(self, minimal_repo_map):
        from repoforge.docs_prompts import get_chapter_prompts
        chapters = get_chapter_prompts(minimal_repo_map, "English", "Test")
        overview = next(c for c in chapters if c["file"] == "01-overview.md")
        assert "FastAPI" in overview["user"] or "Python" in overview["user"]

    def test_api_chapter_included_when_api_imports_present(self, minimal_repo_map):
        from repoforge.docs_prompts import get_chapter_prompts
        # minimal_repo_map has entry_points=["main.py"] → "main" is a server hint
        chapters = get_chapter_prompts(minimal_repo_map, "English", "Test")
        files = [c["file"] for c in chapters]
        assert "06-api-reference.md" in files

    def test_api_chapter_excluded_for_tiny_script(self):
        """A 1-file script with no web signals should not get API reference chapter."""
        from repoforge.docs_prompts import get_chapter_prompts
        repo_map = {
            "root": "/fake",
            "tech_stack": ["Python"],
            "entry_points": [],        # no entry points
            "config_files": [],        # no config files
            "layers": {
                "main": {
                    "path": ".",
                    "modules": [
                        {
                            "path": "process_csv.py", "name": "process_csv",
                            "language": "Python",
                            "exports": ["process"], "imports": ["os", "csv"],
                            "summary_hint": "CSV processing script",
                        }
                    ],
                }
            },
            # total_files < 10 AND no server hints → should skip
            "stats": {"total_files": 1, "by_extension": {".py": 1}, "rg_available": False, "rg_version": None},
        }
        chapters = get_chapter_prompts(repo_map, "English", "Test")
        files = [c["file"] for c in chapters]
        assert "06-api-reference.md" not in files

    def test_data_models_included_for_pydantic(self, minimal_repo_map):
        from repoforge.docs_prompts import get_chapter_prompts
        # minimal_repo_map has 5 total_files → >= 3 → always included
        chapters = get_chapter_prompts(minimal_repo_map, "English", "Test")
        files = [c["file"] for c in chapters]
        assert "05-data-models.md" in files

    def test_data_models_excluded_for_trivial_project(self):
        """A 1-file project should not get data models chapter."""
        from repoforge.docs_prompts import get_chapter_prompts
        repo_map = {
            "root": "/fake",
            "tech_stack": ["Python"],
            "entry_points": [],
            "config_files": [],
            "layers": {"main": {"path": ".", "modules": [
                {"path": "hello.py", "name": "hello", "language": "Python",
                 "exports": ["main"], "imports": [], "summary_hint": "Hello world"},
            ]}},
            "stats": {"total_files": 2, "by_extension": {".py": 2}, "rg_available": False, "rg_version": None},
        }
        chapters = get_chapter_prompts(repo_map, "English", "Test")
        files = [c["file"] for c in chapters]
        assert "05-data-models.md" not in files

    def test_api_chapter_included_for_java_spring_by_stack(self):
        """Java Spring project detected via tech_stack — no imports needed."""
        from repoforge.docs_prompts import get_chapter_prompts
        repo_map = {
            "root": "/fake/java",
            "tech_stack": ["Java", "Spring Boot"],
            "entry_points": ["src/main/java/Application.java"],
            "config_files": ["pom.xml"],
            "layers": {"backend": {"path": "src/main/java", "modules": [
                {"path": "src/main/java/UserController.java", "name": "UserController",
                 "language": "Java", "exports": ["UserController"],
                 "imports": ["org"],   # Java scanner extracts "org", not "spring"
                 "summary_hint": "User REST controller"},
            ]}},
            "stats": {"total_files": 15, "by_extension": {".java": 15}, "rg_available": False, "rg_version": None},
        }
        chapters = get_chapter_prompts(repo_map, "English", "MyApp")
        files = [c["file"] for c in chapters]
        assert "06-api-reference.md" in files

    def test_api_chapter_included_for_go_gin_by_path(self):
        """Go/Gin project detected via controller path — no imports needed."""
        from repoforge.docs_prompts import get_chapter_prompts
        repo_map = {
            "root": "/fake/go",
            "tech_stack": ["Go"],
            "entry_points": ["main.go"],
            "config_files": ["go.mod"],
            "layers": {"main": {"path": ".", "modules": [
                {"path": "internal/handler/user_handler.go", "name": "user_handler",
                 "language": "Go", "exports": ["GetUser", "CreateUser"],
                 "imports": ["github"],   # Go scanner gets "github" not "gin"
                 "summary_hint": "User HTTP handlers"},
                {"path": "internal/handler/product_handler.go", "name": "product_handler",
                 "language": "Go", "exports": ["GetProduct"],
                 "imports": ["github"], "summary_hint": "Product handlers"},
            ]}},
            "stats": {"total_files": 12, "by_extension": {".go": 12}, "rg_available": False, "rg_version": None},
        }
        chapters = get_chapter_prompts(repo_map, "English", "GoService")
        files = [c["file"] for c in chapters]
        assert "06-api-reference.md" in files

    def test_api_chapter_included_for_nestjs_by_path(self):
        """NestJS project detected via controller path — @nestjs/common not extracted cleanly."""
        from repoforge.docs_prompts import get_chapter_prompts
        repo_map = {
            "root": "/fake/nest",
            "tech_stack": ["Node.js", "TypeScript"],
            "entry_points": ["src/main.ts"],
            "config_files": ["package.json"],
            "layers": {"main": {"path": "src", "modules": [
                {"path": "src/users/users.controller.ts", "name": "users.controller",
                 "language": "TypeScript", "exports": ["UsersController"],
                 "imports": ["@nestjs"],   # what the scanner actually extracts
                 "summary_hint": "Users REST controller"},
            ]}},
            "stats": {"total_files": 8, "by_extension": {".ts": 8}, "rg_available": False, "rg_version": None},
        }
        chapters = get_chapter_prompts(repo_map, "English", "NestApp")
        files = [c["file"] for c in chapters]
        assert "06-api-reference.md" in files

    def test_monorepo_architecture_mentions_layers(self, monorepo_map):
        from repoforge.docs_prompts import get_chapter_prompts
        chapters = get_chapter_prompts(monorepo_map, "English", "MyApp")
        files = [c["file"] for c in chapters]
        assert "03-architecture.md" in files
        arch = next(c for c in chapters if c["file"] == "03-architecture.md")
        # Monorepo: architecture prompt should mention multiple layers
        assert "frontend" in arch["user"].lower() or "backend" in arch["user"].lower() or "monorepo" in arch["user"].lower()

    def test_project_name_in_prompts(self, minimal_repo_map):
        from repoforge.docs_prompts import get_chapter_prompts
        chapters = get_chapter_prompts(minimal_repo_map, "English", "AwesomeProject")
        for ch in chapters:
            assert "AwesomeProject" in ch["user"]


# ---------------------------------------------------------------------------
# Tests: docsify
# ---------------------------------------------------------------------------

class TestDocsify:
    def test_generates_three_files(self, tmp_path, minimal_repo_map):
        from repoforge.docsify import build_docsify_files
        from repoforge.docs_prompts import get_chapter_prompts

        chapters = get_chapter_prompts(minimal_repo_map, "English", "TestProject")
        generated = build_docsify_files(tmp_path, "TestProject", chapters)

        assert len(generated) == 3
        names = [Path(f).name for f in generated]
        assert "_sidebar.md" in names
        assert ".nojekyll" in names
        assert "index.html" in names

    def test_all_files_exist_on_disk(self, tmp_path, minimal_repo_map):
        from repoforge.docsify import build_docsify_files
        from repoforge.docs_prompts import get_chapter_prompts

        chapters = get_chapter_prompts(minimal_repo_map, "English", "TestProject")
        generated = build_docsify_files(tmp_path, "TestProject", chapters)

        for f in generated:
            assert Path(f).exists(), f"{f} was not created"

    def test_sidebar_contains_chapter_links(self, tmp_path, minimal_repo_map):
        from repoforge.docsify import build_docsify_files
        from repoforge.docs_prompts import get_chapter_prompts

        chapters = get_chapter_prompts(minimal_repo_map, "English", "TestProject")
        build_docsify_files(tmp_path, "TestProject", chapters)

        sidebar = (tmp_path / "_sidebar.md").read_text()
        assert "Overview" in sidebar
        assert "Quick Start" in sidebar
        # Links should not have .md extension (Docsify convention)
        assert "[Overview](01-overview)" in sidebar

    def test_sidebar_contains_project_name(self, tmp_path, minimal_repo_map):
        from repoforge.docsify import build_docsify_files
        from repoforge.docs_prompts import get_chapter_prompts

        chapters = get_chapter_prompts(minimal_repo_map, "English", "MyAwesomeApp")
        build_docsify_files(tmp_path, "MyAwesomeApp", chapters)

        sidebar = (tmp_path / "_sidebar.md").read_text()
        assert "MyAwesomeApp" in sidebar

    def test_index_html_is_valid_html(self, tmp_path, minimal_repo_map):
        from repoforge.docsify import build_docsify_files
        from repoforge.docs_prompts import get_chapter_prompts

        chapters = get_chapter_prompts(minimal_repo_map, "English", "TestProject")
        build_docsify_files(tmp_path, "TestProject", chapters)

        html = (tmp_path / "index.html").read_text()
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "docsify" in html
        assert "mermaid" in html  # Mermaid support

    def test_index_html_contains_project_name(self, tmp_path, minimal_repo_map):
        from repoforge.docsify import build_docsify_files
        from repoforge.docs_prompts import get_chapter_prompts

        chapters = get_chapter_prompts(minimal_repo_map, "English", "CoolProject")
        build_docsify_files(tmp_path, "CoolProject", chapters)

        html = (tmp_path / "index.html").read_text()
        assert "CoolProject" in html

    def test_spanish_sets_lang_attribute(self, tmp_path, minimal_repo_map):
        from repoforge.docsify import build_docsify_files
        from repoforge.docs_prompts import get_chapter_prompts

        chapters = get_chapter_prompts(minimal_repo_map, "Spanish", "Proyecto")
        build_docsify_files(tmp_path, "Proyecto", chapters, language="Spanish")

        html = (tmp_path / "index.html").read_text()
        assert 'lang="es"' in html

    def test_nojekyll_is_empty(self, tmp_path, minimal_repo_map):
        from repoforge.docsify import build_docsify_files
        from repoforge.docs_prompts import get_chapter_prompts

        chapters = get_chapter_prompts(minimal_repo_map, "English", "Test")
        build_docsify_files(tmp_path, "Test", chapters)

        nojekyll = (tmp_path / ".nojekyll").read_text()
        assert nojekyll == ""

    def test_dark_theme(self, tmp_path, minimal_repo_map):
        from repoforge.docsify import build_docsify_files
        from repoforge.docs_prompts import get_chapter_prompts

        chapters = get_chapter_prompts(minimal_repo_map, "English", "Test")
        build_docsify_files(tmp_path, "Test", chapters, theme="dark")

        html = (tmp_path / "index.html").read_text()
        assert "dark.css" in html

    def test_search_plugin_included(self, tmp_path, minimal_repo_map):
        from repoforge.docsify import build_docsify_files
        from repoforge.docs_prompts import get_chapter_prompts

        chapters = get_chapter_prompts(minimal_repo_map, "English", "Test")
        build_docsify_files(tmp_path, "Test", chapters)

        html = (tmp_path / "index.html").read_text()
        assert "search" in html.lower()


# ---------------------------------------------------------------------------
# Tests: docs_generator (dry-run only — no LLM)
# ---------------------------------------------------------------------------

class TestDocsGenerator:
    def test_dry_run_returns_dict(self, tmp_path):
        from repoforge.docs_generator import generate_docs
        # Use own project dir as test repo
        import os
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_docs(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "docs"),
            language="English",
            dry_run=True,
            verbose=False,
        )
        assert isinstance(result, dict)
        assert result.get("dry_run") is True

    def test_dry_run_no_files_written(self, tmp_path):
        from repoforge.docs_generator import generate_docs
        repo_dir = str(Path(__file__).parent.parent)
        out = tmp_path / "docs"
        generate_docs(
            working_dir=repo_dir,
            output_dir=str(out),
            language="English",
            dry_run=True,
            verbose=False,
        )
        assert not out.exists() or list(out.iterdir()) == []

    def test_dry_run_returns_project_name(self, tmp_path):
        from repoforge.docs_generator import generate_docs
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_docs(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "docs"),
            language="English",
            dry_run=True,
            verbose=False,
        )
        assert "project_name" in result
        assert len(result["project_name"]) > 0

    def test_dry_run_lists_chapters(self, tmp_path):
        from repoforge.docs_generator import generate_docs
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_docs(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "docs"),
            language="English",
            dry_run=True,
            verbose=False,
        )
        assert "chapters" in result
        assert len(result["chapters"]) >= 5
        assert "index.md" in result["chapters"]

    def test_project_name_override(self, tmp_path):
        from repoforge.docs_generator import generate_docs
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_docs(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "docs"),
            project_name="OverrideName",
            language="English",
            dry_run=True,
            verbose=False,
        )
        assert result["project_name"] == "OverrideName"

    def test_language_in_result(self, tmp_path):
        from repoforge.docs_generator import generate_docs
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_docs(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "docs"),
            language="Spanish",
            dry_run=True,
            verbose=False,
        )
        assert result["language"] == "Spanish"


# ---------------------------------------------------------------------------
# Tests: project name inference
# ---------------------------------------------------------------------------

class TestProjectNameInference:
    def test_from_package_json(self, tmp_path):
        import json
        from repoforge.docs_generator import _infer_project_name

        (tmp_path / "package.json").write_text(json.dumps({"name": "my-cool-app"}))
        name = _infer_project_name(tmp_path, {})
        assert name == "My Cool App"

    def test_from_pyproject_toml(self, tmp_path):
        from repoforge.docs_generator import _infer_project_name

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "my-python-lib"\n')
        name = _infer_project_name(tmp_path, {})
        assert name == "My Python Lib"

    def test_fallback_to_dirname(self, tmp_path):
        from repoforge.docs_generator import _infer_project_name

        # No config files
        name = _infer_project_name(tmp_path, {})
        # Should use directory name, title-cased
        assert isinstance(name, str)
        assert len(name) > 0
