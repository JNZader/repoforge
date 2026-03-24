"""
tests/test_scanner_integration.py — Integration tests for repo scanning.

Creates real temp repos with various file types and tests the full
scan pipeline including file discovery, language detection, layer
detection, complexity classification, and config loading.
"""

import json
import subprocess
from pathlib import Path

import pytest

from repoforge.scanner import (
    scan_repo,
    classify_complexity,
    _detect_tech_stack,
    _detect_layers,
    _find_entry_points,
    _find_config_files,
    _ext_to_language,
    _enrich_python,
    _enrich_js,
    _extract_first_comment,
    _load_config,
    LAYER_PATTERNS,
    SUPPORTED_EXTENSIONS,
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
def full_python_repo(tmp_path):
    """A realistic Python project with multiple modules."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "fullapp"\n\n'
        '[project.scripts]\nfullapp = "fullapp.cli:main"\n'
    )
    (tmp_path / "requirements.txt").write_text(
        "fastapi\nuvicorn\npydantic\ncelery\nredis\n"
    )
    pkg = tmp_path / "fullapp"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "cli.py").write_text(
        '"""CLI entry point."""\nimport click\n\ndef main(): pass\n'
    )
    (pkg / "models.py").write_text(
        '"""Data models for the application."""\n'
        'from pydantic import BaseModel\n\n'
        'class User(BaseModel):\n    name: str\n    email: str\n\n'
        'class Item(BaseModel):\n    title: str\n    price: float\n'
    )
    (pkg / "service.py").write_text(
        '"""Business logic services."""\n'
        'from .models import User, Item\n\n'
        'class UserService:\n    def get(self, id): ...\n'
        '    def create(self, data): ...\n\n'
        'class ItemService:\n    def list(self): ...\n'
    )
    (pkg / "routes.py").write_text(
        '"""API routes."""\nfrom fastapi import APIRouter\n\n'
        'router = APIRouter()\n\n'
        '@router.get("/health")\ndef health(): return {"ok": True}\n'
    )
    # Test file (should be deprioritized)
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_models.py").write_text(
        '"""Tests for models."""\nimport pytest\n\ndef test_user(): pass\n'
    )
    _git_init(tmp_path)
    return tmp_path


@pytest.fixture
def js_repo(tmp_path):
    """A realistic JavaScript/TypeScript project."""
    (tmp_path / "package.json").write_text(json.dumps({
        "name": "my-frontend",
        "dependencies": {"react": "18", "next": "14", "zustand": "4"},
        "devDependencies": {"vite": "5"},
    }))
    src = tmp_path / "src"
    src.mkdir()
    (src / "index.ts").write_text(
        '// Main entry point\nexport { App } from "./App";\n'
    )
    (src / "App.tsx").write_text(
        '// Root application component\n'
        'import React from "react";\n'
        'export function App() { return <div>Hello</div>; }\n'
        'export default App;\n'
    )
    hooks = src / "hooks"
    hooks.mkdir()
    (hooks / "useAuth.ts").write_text(
        '// Authentication hook\n'
        'import { useState } from "react";\n'
        'export function useAuth() { return useState(null); }\n'
    )
    (hooks / "useStore.ts").write_text(
        '// Store hook\n'
        'import { create } from "zustand";\n'
        'export const useStore = create(() => ({}));\n'
    )
    _git_init(tmp_path)
    return tmp_path


@pytest.fixture
def multi_lang_repo(tmp_path):
    """Repo with Python, TypeScript, Go, and Rust files."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "multi"\n')
    (tmp_path / "package.json").write_text('{"name": "multi"}')
    (tmp_path / "go.mod").write_text("module multi\n\ngo 1.21\n")
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "multi"\n')
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n")

    (tmp_path / "app.py").write_text('"""Python app."""\ndef main(): pass\n')
    (tmp_path / "index.ts").write_text('export function main() {}\n')
    (tmp_path / "main.go").write_text('package main\nfunc main() {}\n')
    (tmp_path / "main.rs").write_text('fn main() {}\n')
    _git_init(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Full scan pipeline
# ---------------------------------------------------------------------------

class TestScanPipeline:
    def test_full_scan_returns_required_keys(self, full_python_repo):
        repo_map = scan_repo(str(full_python_repo))
        assert "root" in repo_map
        assert "tech_stack" in repo_map
        assert "layers" in repo_map
        assert "entry_points" in repo_map
        assert "config_files" in repo_map
        assert "stats" in repo_map
        assert "repoforge_config" in repo_map

    def test_modules_discovered(self, full_python_repo):
        repo_map = scan_repo(str(full_python_repo))
        all_modules = []
        for layer in repo_map["layers"].values():
            all_modules.extend(layer["modules"])
        assert len(all_modules) > 0
        # Should find at least some of our files
        names = [m["name"] for m in all_modules]
        assert any(n in names for n in ["cli", "models", "service", "routes"])

    def test_python_modules_have_exports(self, full_python_repo):
        repo_map = scan_repo(str(full_python_repo))
        for layer in repo_map["layers"].values():
            for module in layer["modules"]:
                if module["name"] == "models":
                    # Should detect User and Item classes
                    assert len(module["exports"]) > 0

    def test_js_repo_scan(self, js_repo):
        repo_map = scan_repo(str(js_repo))
        assert "React" in repo_map["tech_stack"]
        assert "Next.js" in repo_map["tech_stack"]
        assert len(repo_map["layers"]) >= 1

    def test_multi_lang_tech_stack(self, multi_lang_repo):
        repo_map = scan_repo(str(multi_lang_repo))
        stack = repo_map["tech_stack"]
        assert "Python" in stack
        assert "Node.js" in stack
        assert "Go" in stack
        assert "Rust" in stack
        assert "Docker" in stack


# ---------------------------------------------------------------------------
# Tech stack detection
# ---------------------------------------------------------------------------

class TestTechStackDetection:
    def test_django_detection(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("django\ndjango-rest-framework\n")
        stack = _detect_tech_stack(tmp_path)
        assert "Django" in stack

    def test_flask_detection(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        stack = _detect_tech_stack(tmp_path)
        assert "Flask" in stack

    def test_langchain_detection(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("langchain\nopenai\n")
        stack = _detect_tech_stack(tmp_path)
        assert "LangChain" in stack

    def test_vue_detection(self, tmp_path):
        (tmp_path / "package.json").write_text('{"dependencies": {"vue": "3"}}')
        stack = _detect_tech_stack(tmp_path)
        assert "Vue" in stack

    def test_express_detection(self, tmp_path):
        (tmp_path / "package.json").write_text('{"dependencies": {"express": "4"}}')
        stack = _detect_tech_stack(tmp_path)
        assert "Express" in stack

    def test_terraform_detection(self, tmp_path):
        (tmp_path / "terraform").mkdir()
        stack = _detect_tech_stack(tmp_path)
        assert "Terraform" in stack

    def test_ruby_detection(self, tmp_path):
        (tmp_path / "Gemfile").write_text("source 'https://rubygems.org'\n")
        stack = _detect_tech_stack(tmp_path)
        assert "Ruby" in stack

    def test_java_detection(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project></project>\n")
        stack = _detect_tech_stack(tmp_path)
        assert "Java" in stack

    def test_php_detection(self, tmp_path):
        (tmp_path / "composer.json").write_text("{}")
        stack = _detect_tech_stack(tmp_path)
        assert "PHP" in stack

    def test_deduplication(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        (tmp_path / "requirements.txt").write_text("fastapi\n")
        stack = _detect_tech_stack(tmp_path)
        assert stack.count("Python") == 1


# ---------------------------------------------------------------------------
# Layer detection
# ---------------------------------------------------------------------------

class TestLayerDetection:
    def test_detects_frontend_layer(self, tmp_path):
        (tmp_path / "frontend").mkdir()
        (tmp_path / "frontend" / "index.ts").write_text("")
        layers = _detect_layers(tmp_path, {})
        assert "frontend" in layers

    def test_detects_backend_layer(self, tmp_path):
        (tmp_path / "backend").mkdir()
        (tmp_path / "backend" / "main.py").write_text("")
        layers = _detect_layers(tmp_path, {})
        assert "backend" in layers

    def test_config_override_layers(self, tmp_path):
        (tmp_path / "myapp").mkdir()
        (tmp_path / "myapp" / "app.py").write_text("")
        config = {"layers": {"custom": "myapp"}}
        layers = _detect_layers(tmp_path, config)
        assert "custom" in layers

    def test_fallback_to_main_layer(self, tmp_path):
        (tmp_path / "app.py").write_text("")
        layers = _detect_layers(tmp_path, {})
        assert "main" in layers

    def test_never_layer_dirs_excluded(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        (tmp_path / ".git").mkdir()
        (tmp_path / "app.py").write_text("")
        layers = _detect_layers(tmp_path, {})
        assert "node_modules" not in str(layers)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

class TestEntryPoints:
    def test_detects_main_py(self, tmp_path):
        (tmp_path / "main.py").write_text("")
        eps = _find_entry_points(tmp_path)
        assert "main.py" in eps

    def test_detects_app_py(self, tmp_path):
        (tmp_path / "app.py").write_text("")
        eps = _find_entry_points(tmp_path)
        assert "app.py" in eps

    def test_detects_manage_py(self, tmp_path):
        (tmp_path / "manage.py").write_text("")
        eps = _find_entry_points(tmp_path)
        assert "manage.py" in eps

    def test_detects_from_pyproject_scripts(self, full_python_repo):
        eps = _find_entry_points(full_python_repo)
        assert any("cli" in ep for ep in eps)

    def test_detects_from_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text(
            '{"main": "dist/index.js", "bin": {"cli": "bin/cli.js"}}'
        )
        eps = _find_entry_points(tmp_path)
        assert "dist/index.js" in eps


# ---------------------------------------------------------------------------
# Config files
# ---------------------------------------------------------------------------

class TestConfigFiles:
    def test_finds_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("")
        configs = _find_config_files(tmp_path)
        assert "pyproject.toml" in configs

    def test_finds_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")
        configs = _find_config_files(tmp_path)
        assert "package.json" in configs

    def test_finds_docker_compose(self, tmp_path):
        (tmp_path / "docker-compose.yml").write_text("")
        configs = _find_config_files(tmp_path)
        assert "docker-compose.yml" in configs

    def test_finds_repoforge_yaml(self, tmp_path):
        (tmp_path / "repoforge.yaml").write_text("")
        configs = _find_config_files(tmp_path)
        assert "repoforge.yaml" in configs


# ---------------------------------------------------------------------------
# Complexity classification
# ---------------------------------------------------------------------------

class TestComplexityClassification:
    def test_small_repo(self):
        repo_map = {
            "stats": {"total_files": 5},
            "layers": {"main": {"modules": [{}] * 3}},
        }
        cx = classify_complexity(repo_map)
        assert cx["size"] == "small"
        assert cx["generate_orchestrator"] is False
        assert cx["max_chapters"] == 5

    def test_medium_repo(self):
        repo_map = {
            "stats": {"total_files": 50},
            "layers": {
                "backend": {"modules": [{}] * 20},
                "frontend": {"modules": [{}] * 15},
            },
        }
        cx = classify_complexity(repo_map)
        assert cx["size"] == "medium"
        assert cx["generate_orchestrator"] is True

    def test_large_repo(self):
        repo_map = {
            "stats": {"total_files": 500},
            "layers": {k: {"modules": [{}] * 30} for k in [
                "frontend", "backend", "shared", "infra", "workers", "mobile"
            ]},
        }
        cx = classify_complexity(repo_map)
        assert cx["size"] == "large"
        assert cx["prompt_detail"] == "concise"

    def test_override_small(self):
        repo_map = {
            "stats": {"total_files": 500},
            "layers": {"a": {"modules": []}, "b": {"modules": []}, "c": {"modules": []}},
        }
        cx = classify_complexity(repo_map, override="small")
        assert cx["size"] == "small"

    def test_override_large(self):
        repo_map = {
            "stats": {"total_files": 5},
            "layers": {"main": {"modules": []}},
        }
        cx = classify_complexity(repo_map, override="large")
        assert cx["size"] == "large"


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

class TestLanguageDetection:
    @pytest.mark.parametrize("ext,lang", [
        (".py", "Python"),
        (".ts", "TypeScript"),
        (".tsx", "TypeScript"),
        (".js", "JavaScript"),
        (".jsx", "JavaScript"),
        (".go", "Go"),
        (".rs", "Rust"),
        (".java", "Java"),
        (".rb", "Ruby"),
        (".cs", "C#"),
        (".cpp", "C++"),
        (".c", "C"),
        (".h", "C/C++"),
        (".php", "PHP"),
        (".swift", "Swift"),
        (".kt", "Kotlin"),
    ])
    def test_extension_mapping(self, ext, lang):
        assert _ext_to_language(ext) == lang

    def test_unknown_extension(self):
        assert _ext_to_language(".xyz") == "Unknown"


# ---------------------------------------------------------------------------
# JS enrichment
# ---------------------------------------------------------------------------

class TestJSEnrichment:
    def test_extracts_exports(self):
        content = (
            'export function fetchData() {}\n'
            'export class ApiClient {}\n'
            'export const CONFIG = {};\n'
            'export async function loadUser() {}\n'
        )
        module = {"exports": [], "imports": [], "summary_hint": ""}
        _enrich_js(module, content)
        assert "fetchData" in module["exports"]
        assert "ApiClient" in module["exports"]
        assert "CONFIG" in module["exports"]
        assert "loadUser" in module["exports"]

    def test_extracts_imports(self):
        content = (
            'import React from "react";\n'
            'import { useState } from "react";\n'
            'import { create } from "zustand";\n'
            'import { helper } from "./utils";\n'
        )
        module = {"exports": [], "imports": [], "summary_hint": ""}
        _enrich_js(module, content)
        assert "react" in module["imports"]
        assert "zustand" in module["imports"]
        # Relative imports excluded
        assert "./utils" not in module["imports"]


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

class TestConfigLoading:
    def test_loads_repoforge_yaml(self, tmp_path):
        (tmp_path / "repoforge.yaml").write_text("language: Spanish\nmodel: gpt-4o\n")
        config = _load_config(tmp_path)
        assert config["language"] == "Spanish"
        assert config["model"] == "gpt-4o"

    def test_loads_repoforge_yml(self, tmp_path):
        (tmp_path / "repoforge.yml").write_text("complexity: large\n")
        config = _load_config(tmp_path)
        assert config["complexity"] == "large"

    def test_loads_codeviewx_yaml(self, tmp_path):
        (tmp_path / "codeviewx.yaml").write_text("model: claude\n")
        config = _load_config(tmp_path)
        assert config["model"] == "claude"

    def test_no_config_returns_empty(self, tmp_path):
        config = _load_config(tmp_path)
        assert config == {}

    def test_priority_repoforge_over_codeviewx(self, tmp_path):
        (tmp_path / "repoforge.yaml").write_text("model: first\n")
        (tmp_path / "codeviewx.yaml").write_text("model: second\n")
        config = _load_config(tmp_path)
        assert config["model"] == "first"


# ---------------------------------------------------------------------------
# Extract first comment
# ---------------------------------------------------------------------------

class TestExtractFirstComment:
    def test_python_comment(self):
        assert len(_extract_first_comment("# This is a Python module\ndef foo(): pass")) > 0

    def test_js_comment(self):
        assert len(_extract_first_comment("// This is a JavaScript module\nfunction foo() {}")) > 0

    def test_no_comment(self):
        assert _extract_first_comment("def foo(): pass") == ""

    def test_short_comment_ignored(self):
        assert _extract_first_comment("# Hi") == ""
