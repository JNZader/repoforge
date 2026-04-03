"""
tests/test_prompts_cmd.py - Tests for analysis prompts generation.

Tests cover:
- AnalysisPrompt dataclass creation
- PROMPT_TYPES constant completeness
- generate_prompts() with mocked scanner data
- Type filtering (single, multiple, all)
- Invalid type rejection
- render_prompts_markdown() output structure
- write_individual_prompts() file creation
- Individual prompt builder content checks
- CLI integration via CliRunner
- Helper functions (_is_test_module, _test_target_name, _source_test_name)
"""

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner


# ---------------------------------------------------------------------------
# Fixtures: mock scanner data
# ---------------------------------------------------------------------------

MOCK_REPO_MAP = {
    "root": "/tmp/fake-repo",
    "tech_stack": ["Python", "FastAPI"],
    "layers": {
        "core": {
            "path": "src/core",
            "modules": [
                {
                    "path": "src/core/models.py",
                    "name": "models",
                    "exports": ["User", "Post", "Comment", "Tag", "Category"],
                    "imports": [],
                },
                {
                    "path": "src/core/auth.py",
                    "name": "auth",
                    "exports": ["authenticate", "hash_password"],
                    "imports": ["User"],
                },
                {
                    "path": "src/core/utils.py",
                    "name": "utils",
                    "exports": ["slugify"],
                    "imports": [],
                },
            ],
        },
        "api": {
            "path": "src/api",
            "modules": [
                {
                    "path": "src/api/routes.py",
                    "name": "routes",
                    "exports": ["router"],
                    "imports": ["User", "authenticate"],
                },
            ],
        },
        "tests": {
            "path": "tests",
            "modules": [
                {
                    "path": "tests/test_models.py",
                    "name": "test_models",
                    "exports": ["TestUser"],
                    "imports": ["User"],
                },
            ],
        },
    },
    "entry_points": ["src/main.py"],
    "config_files": ["pyproject.toml", "requirements.txt"],
    "stats": {"total_files": 5},
}


@pytest.fixture
def mock_scan():
    """Patch scan_repo to return mock data."""
    with patch("repoforge.prompts_cmd.scan_repo", return_value=MOCK_REPO_MAP):
        yield


# ---------------------------------------------------------------------------
# Data model tests
# ---------------------------------------------------------------------------


class TestAnalysisPrompt:
    def test_creation(self):
        from repoforge.prompts_cmd import AnalysisPrompt

        p = AnalysisPrompt(
            prompt_type="security",
            title="Security Review",
            body="Check for vulnerabilities",
        )
        assert p.prompt_type == "security"
        assert p.title == "Security Review"
        assert p.body == "Check for vulnerabilities"
        assert p.files == []

    def test_with_files(self):
        from repoforge.prompts_cmd import AnalysisPrompt

        p = AnalysisPrompt(
            prompt_type="solid",
            title="SOLID",
            body="body",
            files=["a.py", "b.py"],
        )
        assert p.files == ["a.py", "b.py"]


class TestPromptTypes:
    def test_all_types_present(self):
        from repoforge.prompts_cmd import PROMPT_TYPES, _BUILDERS

        assert len(PROMPT_TYPES) == 7
        for t in PROMPT_TYPES:
            assert t in _BUILDERS, f"Missing builder for type: {t}"

    def test_types_are_strings(self):
        from repoforge.prompts_cmd import PROMPT_TYPES

        for t in PROMPT_TYPES:
            assert isinstance(t, str)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_is_test_module(self):
        from repoforge.prompts_cmd import _is_test_module

        assert _is_test_module("tests/test_foo.py") is True
        assert _is_test_module("src/foo.test.ts") is True
        assert _is_test_module("src/__tests__/bar.js") is True
        assert _is_test_module("src/foo_test.go") is True
        assert _is_test_module("src/core/models.py") is False
        assert _is_test_module("src/utils.py") is False

    def test_test_target_name(self):
        from repoforge.prompts_cmd import _test_target_name

        assert _test_target_name("tests/test_models.py") == "models"
        assert _test_target_name("src/foo_test.go") == "foo"
        assert _test_target_name("src/bar.test.ts") == "bar"
        assert _test_target_name("src/baz.spec.js") == "baz"

    def test_source_test_name(self):
        from repoforge.prompts_cmd import _source_test_name

        assert _source_test_name("src/core/models.py") == "models"
        assert _source_test_name("src/api/routes.ts") == "routes"


# ---------------------------------------------------------------------------
# generate_prompts tests
# ---------------------------------------------------------------------------


class TestGeneratePrompts:
    def test_generate_all(self, mock_scan):
        from repoforge.prompts_cmd import generate_prompts

        result = generate_prompts("/tmp/fake-repo")
        assert len(result) == 7
        types = {p.prompt_type for p in result}
        assert "solid" in types
        assert "security" in types
        assert "architecture" in types
        assert "dead-code" in types
        assert "test-gaps" in types
        assert "performance" in types
        assert "deps" in types

    def test_generate_filtered(self, mock_scan):
        from repoforge.prompts_cmd import generate_prompts

        result = generate_prompts("/tmp/fake-repo", types=["security", "solid"])
        assert len(result) == 2
        types = {p.prompt_type for p in result}
        assert types == {"security", "solid"}

    def test_generate_single(self, mock_scan):
        from repoforge.prompts_cmd import generate_prompts

        result = generate_prompts("/tmp/fake-repo", types=["architecture"])
        assert len(result) == 1
        assert result[0].prompt_type == "architecture"

    def test_invalid_type_raises(self, mock_scan):
        from repoforge.prompts_cmd import generate_prompts

        with pytest.raises(ValueError, match="Unknown prompt type"):
            generate_prompts("/tmp/fake-repo", types=["nonexistent"])

    def test_prompts_have_content(self, mock_scan):
        from repoforge.prompts_cmd import generate_prompts

        result = generate_prompts("/tmp/fake-repo")
        for p in result:
            assert p.title, f"{p.prompt_type} has no title"
            assert p.body, f"{p.prompt_type} has no body"
            assert len(p.body) > 50, f"{p.prompt_type} body too short"


# ---------------------------------------------------------------------------
# Prompt builder content tests
# ---------------------------------------------------------------------------


class TestPromptContent:
    def test_solid_references_exports(self, mock_scan):
        from repoforge.prompts_cmd import generate_prompts

        result = generate_prompts("/tmp/fake-repo", types=["solid"])
        body = result[0].body
        assert "SOLID" in body
        assert "Single Responsibility" in body
        assert "exports" in body.lower()

    def test_security_detects_auth_files(self, mock_scan):
        from repoforge.prompts_cmd import generate_prompts

        result = generate_prompts("/tmp/fake-repo", types=["security"])
        body = result[0].body
        assert "auth" in body.lower()
        assert "Authentication" in body

    def test_architecture_shows_layers(self, mock_scan):
        from repoforge.prompts_cmd import generate_prompts

        result = generate_prompts("/tmp/fake-repo", types=["architecture"])
        body = result[0].body
        assert "core" in body
        assert "api" in body

    def test_test_gaps_counts_modules(self, mock_scan):
        from repoforge.prompts_cmd import generate_prompts

        result = generate_prompts("/tmp/fake-repo", types=["test-gaps"])
        body = result[0].body
        assert "Source modules:" in body
        assert "Test modules:" in body

    def test_deps_mentions_manifests(self, mock_scan):
        from repoforge.prompts_cmd import generate_prompts

        result = generate_prompts("/tmp/fake-repo", types=["deps"])
        body = result[0].body
        assert "pyproject.toml" in body or "requirements.txt" in body


# ---------------------------------------------------------------------------
# Rendering tests
# ---------------------------------------------------------------------------


class TestRendering:
    def test_render_markdown(self, mock_scan):
        from repoforge.prompts_cmd import generate_prompts, render_prompts_markdown

        result = generate_prompts("/tmp/fake-repo", types=["security"])
        md = render_prompts_markdown(result)
        assert "# Analysis Prompts" in md
        assert "## 1." in md
        assert "Security Review" in md

    def test_render_markdown_multiple(self, mock_scan):
        from repoforge.prompts_cmd import generate_prompts, render_prompts_markdown

        result = generate_prompts("/tmp/fake-repo", types=["security", "solid"])
        md = render_prompts_markdown(result)
        assert "## 1." in md
        assert "## 2." in md

    def test_write_individual(self, mock_scan, tmp_path):
        from repoforge.prompts_cmd import generate_prompts, write_individual_prompts

        result = generate_prompts("/tmp/fake-repo", types=["security", "solid"])
        written = write_individual_prompts(result, str(tmp_path))
        assert len(written) == 2

        files = list(tmp_path.iterdir())
        names = {f.name for f in files}
        assert "security.txt" in names
        assert "solid.txt" in names

        # Check files have content
        for f in files:
            content = f.read_text()
            assert len(content) > 50

    def test_write_creates_directory(self, mock_scan, tmp_path):
        from repoforge.prompts_cmd import generate_prompts, write_individual_prompts

        result = generate_prompts("/tmp/fake-repo", types=["security"])
        outdir = tmp_path / "nested" / "prompts"
        written = write_individual_prompts(result, str(outdir))
        assert len(written) == 1
        assert outdir.exists()


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_help(self):
        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["prompts", "--help"])
        assert result.exit_code == 0
        assert "analysis prompts" in result.output.lower()
        assert "--type" in result.output

    def test_invalid_type(self):
        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["prompts", "-w", ".", "--type", "bogus"])
        assert result.exit_code == 1
        assert "Unknown prompt type" in result.output

    def test_prompts_stdout(self, mock_scan):
        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["prompts", "-w", ".", "--type", "security", "-q"])
        assert result.exit_code == 0
        assert "Security Review" in result.output
        assert "# Analysis Prompts" in result.output

    def test_prompts_output_dir(self, mock_scan, tmp_path):
        from repoforge.cli import main

        runner = CliRunner()
        outdir = str(tmp_path / "prompts")
        result = runner.invoke(
            main, ["prompts", "-w", ".", "-o", outdir, "--type", "security,solid", "-q"],
        )
        assert result.exit_code == 0
        assert (tmp_path / "prompts" / "security.txt").exists()
        assert (tmp_path / "prompts" / "solid.txt").exists()


# ---------------------------------------------------------------------------
# Public API exports test
# ---------------------------------------------------------------------------


class TestPublicAPI:
    def test_exports_available(self):
        from repoforge import (
            AnalysisPrompt,
            PROMPT_TYPES,
            generate_prompts,
            render_prompts_markdown,
            write_individual_prompts,
        )

        assert AnalysisPrompt is not None
        assert len(PROMPT_TYPES) == 7
        assert callable(generate_prompts)
        assert callable(render_prompts_markdown)
        assert callable(write_individual_prompts)
