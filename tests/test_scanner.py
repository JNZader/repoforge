"""
tests/test_scanner.py - Tests for the deterministic scanner (no LLM needed).
"""

import os
import ast
from pathlib import Path
import pytest
import tempfile

from repoforge.scanner import scan_repo, _detect_tech_stack, _enrich_python


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_python_repo(tmp_path):
    """Create a minimal Python repo in a temp dir."""
    # pyproject.toml
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "myapp"\n')

    # main app
    (tmp_path / "app.py").write_text("""\
\"\"\"Main FastAPI application.\"\"\"
from fastapi import FastAPI
from .routers import users, items

app = FastAPI()
app.include_router(users.router)
app.include_router(items.router)

def create_app():
    return app
""")

    # routers dir
    routers = tmp_path / "routers"
    routers.mkdir()
    (routers / "__init__.py").write_text("")
    (routers / "users.py").write_text("""\
\"\"\"User management endpoints.\"\"\"
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/users")

def get_users():
    return []

def create_user(data: dict):
    return data

class UserService:
    def list(self): ...
    def get(self, id): ...
""")

    return tmp_path


@pytest.fixture
def monorepo(tmp_path):
    """Simulate a monorepo with frontend + backend layers."""
    (tmp_path / "package.json").write_text('{"dependencies": {"next": "14.0", "react": "18.0"}}')
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "api"\n')

    fe = tmp_path / "apps" / "web"
    fe.mkdir(parents=True)
    (fe / "index.ts").write_text("// Next.js entry\nexport default function Home() {}")

    be = tmp_path / "apps" / "api"
    be.mkdir(parents=True)
    (be / "main.py").write_text('"""FastAPI backend."""\nfrom fastapi import FastAPI\napp = FastAPI()\n')

    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTechStackDetection:
    def test_detects_python(self, simple_python_repo):
        stack = _detect_tech_stack(simple_python_repo)
        assert "Python" in stack

    def test_detects_fastapi(self, simple_python_repo):
        # Add fastapi to requirements
        (simple_python_repo / "requirements.txt").write_text("fastapi\nuvicorn\n")
        stack = _detect_tech_stack(simple_python_repo)
        assert "FastAPI" in stack

    def test_detects_next_from_package_json(self, monorepo):
        stack = _detect_tech_stack(monorepo)
        assert "Next.js" in stack
        assert "React" in stack

    def test_detects_docker(self, tmp_path):
        (tmp_path / "Dockerfile").write_text("FROM python:3.12\n")
        stack = _detect_tech_stack(tmp_path)
        assert "Docker" in stack


class TestPythonEnrichment:
    def test_extracts_exports(self):
        content = """\
\"\"\"User module.\"\"\"
def get_users(): pass
def create_user(data): pass
class UserService: pass
def _private(): pass
"""
        module = {"exports": [], "imports": [], "summary_hint": ""}
        _enrich_python(module, content)
        assert "get_users" in module["exports"]
        assert "create_user" in module["exports"]
        assert "UserService" in module["exports"]
        assert "_private" not in module["exports"]

    def test_extracts_docstring(self):
        content = '"""User management module."""\ndef foo(): pass\n'
        module = {"exports": [], "imports": [], "summary_hint": ""}
        _enrich_python(module, content)
        assert "User management module" in module["summary_hint"]

    def test_extracts_external_imports(self):
        content = "import fastapi\nfrom pydantic import BaseModel\nfrom .local import thing\n"
        module = {"exports": [], "imports": [], "summary_hint": ""}
        _enrich_python(module, content)
        assert "fastapi" in module["imports"]
        assert "pydantic" in module["imports"]
        # relative imports should be excluded
        assert ".local" not in module["imports"]
        assert "local" not in module["imports"]

    def test_handles_syntax_error_gracefully(self):
        module = {"exports": [], "imports": [], "summary_hint": ""}
        _enrich_python(module, "def broken(:\n    pass\n")
        # Should not raise


class TestScanRepo:
    def test_basic_scan(self, simple_python_repo):
        repo_map = scan_repo(str(simple_python_repo))
        assert repo_map["root"] == str(simple_python_repo)
        assert isinstance(repo_map["tech_stack"], list)
        assert isinstance(repo_map["layers"], dict)

    def test_detects_entry_points(self, simple_python_repo):
        repo_map = scan_repo(str(simple_python_repo))
        assert "app.py" in repo_map["entry_points"]

    def test_monorepo_layer_detection(self, monorepo):
        repo_map = scan_repo(str(monorepo))
        layers = repo_map["layers"]
        # Should detect at least one layer from apps/web or apps/api
        assert len(layers) >= 1

    def test_modules_have_required_fields(self, simple_python_repo):
        repo_map = scan_repo(str(simple_python_repo))
        for layer_data in repo_map["layers"].values():
            for module in layer_data["modules"]:
                assert "path" in module
                assert "name" in module
                assert "language" in module
                assert "exports" in module
                assert "imports" in module
