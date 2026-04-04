"""
tests/test_exporter.py - Tests for the LLM view export feature.

Tests cover:
- export_llm_view: markdown and XML output, token budgeting, no-contents mode
- Directory tree generation
- File prioritization
- CLI integration (Click runner)
"""

import pytest

from repoforge.exporter import (
    _build_tree,
    _discover_all_files,
    _estimate_tokens,
    _prioritize_files,
    _xml_escape,
    export_llm_view,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_repo(tmp_path):
    """Create a minimal Python repo for testing."""
    # pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test-project"\n'
        '[project.scripts]\nmyapp = "myapp.cli:main"\n'
    )

    # Source files
    src = tmp_path / "myapp"
    src.mkdir()
    (src / "__init__.py").write_text('"""My test application."""\n')
    (src / "cli.py").write_text(
        '"""CLI entry point."""\n'
        "import click\n\n"
        "def main():\n"
        '    print("hello")\n'
    )
    (src / "core.py").write_text(
        '"""Core business logic."""\n'
        "import json\n\n"
        "def process(data: dict) -> dict:\n"
        "    return data\n\n"
        "class Processor:\n"
        "    pass\n"
    )

    # Config
    (tmp_path / "README.md").write_text("# Test Project\n\nA test project.\n")
    (tmp_path / ".gitignore").write_text("__pycache__/\n*.pyc\n")

    # Test file
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_core.py").write_text(
        '"""Tests for core module."""\n'
        "def test_process():\n"
        "    assert True\n"
    )

    # A file that should be skipped (binary extension)
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n")

    # A lockfile that should be skipped
    (tmp_path / "package-lock.json").write_text('{"lockfileVersion": 3}')

    return tmp_path


@pytest.fixture
def sample_repo_map():
    """A minimal repo map matching sample_repo structure."""
    return {
        "root": "/fake/project",
        "tech_stack": ["Python"],
        "entry_points": ["myapp/cli.py"],
        "config_files": ["pyproject.toml"],
        "layers": {
            "main": {
                "path": ".",
                "modules": [
                    {
                        "path": "myapp/cli.py",
                        "name": "cli",
                        "language": "Python",
                        "exports": ["main"],
                        "imports": ["click"],
                        "summary_hint": "CLI entry point",
                    },
                    {
                        "path": "myapp/core.py",
                        "name": "core",
                        "language": "Python",
                        "exports": ["process", "Processor"],
                        "imports": ["json"],
                        "summary_hint": "Core business logic",
                    },
                ],
            }
        },
        "stats": {
            "total_files": 3,
            "by_extension": {".py": 3},
            "rg_available": False,
            "rg_version": None,
        },
    }


# ---------------------------------------------------------------------------
# Tests: export_llm_view (markdown format)
# ---------------------------------------------------------------------------

class TestExportMarkdown:
    def test_returns_string(self, sample_repo):
        result = export_llm_view(str(sample_repo))
        assert isinstance(result, str)
        assert len(result) > 100

    def test_contains_project_name(self, sample_repo):
        result = export_llm_view(str(sample_repo))
        assert sample_repo.name in result

    def test_contains_llm_context_header(self, sample_repo):
        result = export_llm_view(str(sample_repo))
        assert "LLM Context" in result

    def test_contains_project_overview(self, sample_repo):
        result = export_llm_view(str(sample_repo))
        assert "## Project Overview" in result
        assert "Tech stack" in result

    def test_contains_directory_tree(self, sample_repo):
        result = export_llm_view(str(sample_repo))
        assert "## Directory Tree" in result
        assert "myapp" in result

    def test_contains_file_contents(self, sample_repo):
        result = export_llm_view(str(sample_repo))
        assert "## File Contents" in result
        # Actual source code should be present
        assert "def main():" in result or "def process(" in result

    def test_contains_definitions(self, sample_repo):
        result = export_llm_view(str(sample_repo))
        # Either in Key Definitions or in file contents
        assert "process" in result
        assert "Processor" in result or "main" in result

    def test_skips_binary_files(self, sample_repo):
        result = export_llm_view(str(sample_repo))
        assert "logo.png" not in result

    def test_skips_lockfiles(self, sample_repo):
        result = export_llm_view(str(sample_repo))
        assert "package-lock.json" not in result
        assert "lockfileVersion" not in result

    def test_writes_to_file(self, sample_repo, tmp_path):
        output = tmp_path / "output" / "context.md"
        result = export_llm_view(str(sample_repo), output_path=str(output))
        assert output.exists()
        assert output.read_text() == result

    def test_creates_parent_dirs(self, sample_repo, tmp_path):
        output = tmp_path / "deep" / "nested" / "context.md"
        export_llm_view(str(sample_repo), output_path=str(output))
        assert output.exists()


# ---------------------------------------------------------------------------
# Tests: no-contents mode
# ---------------------------------------------------------------------------

class TestNoContents:
    def test_no_file_contents_section(self, sample_repo):
        result = export_llm_view(str(sample_repo), include_contents=False)
        assert "## File Contents" not in result

    def test_still_has_tree(self, sample_repo):
        result = export_llm_view(str(sample_repo), include_contents=False)
        assert "## Directory Tree" in result

    def test_still_has_overview(self, sample_repo):
        result = export_llm_view(str(sample_repo), include_contents=False)
        assert "## Project Overview" in result

    def test_much_shorter_than_full(self, sample_repo):
        full = export_llm_view(str(sample_repo), include_contents=True)
        brief = export_llm_view(str(sample_repo), include_contents=False)
        assert len(brief) < len(full)


# ---------------------------------------------------------------------------
# Tests: token budget limiting
# ---------------------------------------------------------------------------

class TestTokenBudget:
    def test_respects_max_tokens(self, sample_repo):
        # Very small budget — should truncate
        result = export_llm_view(str(sample_repo), max_tokens=500)
        # 500 tokens * 4 chars/token = 2000 chars
        assert len(result) < 5000  # generous margin for header

    def test_budget_includes_truncation_comment(self, sample_repo):
        result = export_llm_view(str(sample_repo), max_tokens=500)
        # Should include a comment about omitted files
        assert "omitted" in result.lower() or "budget" in result.lower() or len(result) < 3000

    def test_no_budget_includes_all_files(self, sample_repo):
        result = export_llm_view(str(sample_repo), max_tokens=None)
        # Should include contents from multiple files
        assert "def main():" in result or "def process(" in result

    def test_large_budget_same_as_no_budget(self, sample_repo):
        full = export_llm_view(str(sample_repo), max_tokens=None)
        large = export_llm_view(str(sample_repo), max_tokens=1_000_000)
        assert len(large) == len(full)


# ---------------------------------------------------------------------------
# Tests: XML format
# ---------------------------------------------------------------------------

class TestExportXML:
    def test_returns_xml_string(self, sample_repo):
        result = export_llm_view(str(sample_repo), fmt="xml")
        assert result.startswith("<repository")
        assert result.strip().endswith("</repository>")

    def test_contains_overview_tag(self, sample_repo):
        result = export_llm_view(str(sample_repo), fmt="xml")
        assert "<overview>" in result
        assert "<tech_stack>" in result

    def test_contains_tree_tag(self, sample_repo):
        result = export_llm_view(str(sample_repo), fmt="xml")
        assert "<tree>" in result

    def test_contains_files_tag(self, sample_repo):
        result = export_llm_view(str(sample_repo), fmt="xml")
        assert "<files>" in result
        assert '<file path="' in result

    def test_xml_escapes_content(self, tmp_path):
        """Ensure XML special characters are properly escaped."""
        (tmp_path / "test.py").write_text('x = 1 < 2 and 3 > 1\nprint("a & b")\n')
        result = export_llm_view(str(tmp_path), fmt="xml")
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result

    def test_no_contents_xml(self, sample_repo):
        result = export_llm_view(str(sample_repo), fmt="xml", include_contents=False)
        assert "<files>" not in result
        assert "<tree>" in result

    def test_token_budget_xml(self, sample_repo):
        result = export_llm_view(str(sample_repo), fmt="xml", max_tokens=500)
        assert "<repository" in result
        assert "</repository>" in result


# ---------------------------------------------------------------------------
# Tests: directory tree builder
# ---------------------------------------------------------------------------

class TestBuildTree:
    def test_basic_tree(self, tmp_path):
        files = [
            tmp_path / "a.py",
            tmp_path / "b.py",
            tmp_path / "sub" / "c.py",
        ]
        for f in files:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.touch()

        tree = _build_tree(tmp_path, files)
        assert tmp_path.name in tree
        assert "a.py" in tree
        assert "sub" in tree
        assert "c.py" in tree

    def test_empty_file_list(self, tmp_path):
        tree = _build_tree(tmp_path, [])
        assert tmp_path.name in tree

    def test_nested_dirs(self, tmp_path):
        f = tmp_path / "a" / "b" / "c" / "deep.py"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.touch()

        tree = _build_tree(tmp_path, [f])
        assert "deep.py" in tree
        assert "a" in tree


# ---------------------------------------------------------------------------
# Tests: file discovery
# ---------------------------------------------------------------------------

class TestDiscoverFiles:
    def test_finds_source_files(self, sample_repo):
        files = _discover_all_files(sample_repo)
        names = [f.name for f in files]
        assert "cli.py" in names
        assert "core.py" in names

    def test_finds_config_files(self, sample_repo):
        files = _discover_all_files(sample_repo)
        names = [f.name for f in files]
        assert "pyproject.toml" in names
        assert "README.md" in names

    def test_skips_binary(self, sample_repo):
        files = _discover_all_files(sample_repo)
        names = [f.name for f in files]
        assert "logo.png" not in names

    def test_skips_lockfiles(self, sample_repo):
        files = _discover_all_files(sample_repo)
        names = [f.name for f in files]
        assert "package-lock.json" not in names

    def test_skips_git_dir(self, sample_repo):
        git_dir = sample_repo / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]\n")
        files = _discover_all_files(sample_repo)
        paths = [str(f) for f in files]
        assert not any(".git/" in p or ".git\\" in p for p in paths)

    def test_empty_dir(self, tmp_path):
        files = _discover_all_files(tmp_path)
        assert files == []


# ---------------------------------------------------------------------------
# Tests: file prioritization
# ---------------------------------------------------------------------------

class TestPrioritizeFiles:
    def test_entry_points_come_first(self, sample_repo, sample_repo_map):
        files = _discover_all_files(sample_repo)
        ordered = _prioritize_files(files, sample_repo, sample_repo_map)
        # Entry point should be in the first few files
        names = [f.name for f in ordered[:5]]
        # pyproject.toml (config) or cli.py (entry) should be early
        assert "cli.py" in names or "pyproject.toml" in names

    def test_tests_come_later(self, sample_repo, sample_repo_map):
        files = _discover_all_files(sample_repo)
        ordered = _prioritize_files(files, sample_repo, sample_repo_map)
        names = [f.name for f in ordered]
        if "test_core.py" in names and "core.py" in names:
            assert names.index("core.py") < names.index("test_core.py")


# ---------------------------------------------------------------------------
# Tests: helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_estimate_tokens(self):
        assert _estimate_tokens("a" * 400) == 100
        assert _estimate_tokens("") == 0

    def test_xml_escape(self):
        assert _xml_escape("<>&\"") == "&lt;&gt;&amp;&quot;"
        assert _xml_escape("hello") == "hello"


# ---------------------------------------------------------------------------
# Tests: CLI integration
# ---------------------------------------------------------------------------

class TestExportCLI:
    def test_cli_export_to_stdout(self, sample_repo):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["export", "-w", str(sample_repo), "-q"])
        assert result.exit_code == 0
        assert "LLM Context" in result.output

    def test_cli_export_to_file(self, sample_repo, tmp_path):
        from click.testing import CliRunner

        from repoforge.cli import main

        output = tmp_path / "out.md"
        runner = CliRunner()
        result = runner.invoke(main, [
            "export", "-w", str(sample_repo), "-o", str(output), "-q",
        ])
        assert result.exit_code == 0
        assert output.exists()
        content = output.read_text()
        assert "LLM Context" in content

    def test_cli_export_xml(self, sample_repo):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "export", "-w", str(sample_repo), "--format", "xml", "-q",
        ])
        assert result.exit_code == 0
        assert "<repository" in result.output

    def test_cli_export_no_contents(self, sample_repo):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "export", "-w", str(sample_repo), "--no-contents", "-q",
        ])
        assert result.exit_code == 0
        assert "## File Contents" not in result.output
        assert "## Directory Tree" in result.output

    def test_cli_export_max_tokens(self, sample_repo):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "export", "-w", str(sample_repo), "--max-tokens", "500", "-q",
        ])
        assert result.exit_code == 0

    def test_cli_help(self):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["export", "--help"])
        assert result.exit_code == 0
        assert "Flatten" in result.output or "LLM" in result.output
