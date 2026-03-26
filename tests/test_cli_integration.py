"""
tests/test_cli_integration.py — Integration tests for the CLI interface.

Exercises real CLI commands via Click's CliRunner against actual
temp repos. No mocks except where LLM calls are involved.
"""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from repoforge.cli import main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_repo(tmp_path):
    """Create a minimal Python repo with git init."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "sample-project"\nversion = "0.1.0"\n'
    )
    (tmp_path / "main.py").write_text(
        '"""Main module."""\n\ndef hello():\n    return "world"\n'
    )
    (tmp_path / "utils.py").write_text(
        '"""Utilities."""\nimport os\n\ndef helper():\n    pass\n'
    )
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text(
        '"""App entry."""\nfrom main import hello\n\ndef run():\n    hello()\n'
    )
    # Initialize git so scanner works properly
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, capture_output=True,
    )
    subprocess.run(
        ["git", "add", "."], cwd=tmp_path, capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True,
    )
    return tmp_path


@pytest.fixture
def sample_skill(tmp_path):
    """Create a sample SKILL.md for scoring."""
    skills_dir = tmp_path / ".claude" / "skills" / "backend"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("""\
---
name: backend-skill
description: >
  Backend development patterns for the sample project.
  Trigger: When working with Python backend code.
globs:
  - "**/*.py"
---

## Critical Rules

1. Always use type hints for function parameters and return types.
2. Use dependency injection for services.
3. Handle errors with specific exception types.

## Patterns

### Service Pattern

```python
class UserService:
    def __init__(self, db: Database):
        self.db = db

    async def get_user(self, user_id: int) -> User:
        return await self.db.get(User, user_id)
```

## Anti-Patterns

### Don't use raw SQL queries

```python
# BAD
db.execute(f"SELECT * FROM users WHERE id = {user_id}")

# GOOD
db.execute("SELECT * FROM users WHERE id = ?", [user_id])
```

## Testing

Run tests with: `pytest tests/ -x`
""")
    return tmp_path


# ---------------------------------------------------------------------------
# Help & version
# ---------------------------------------------------------------------------

class TestHelpAndVersion:
    def test_root_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "RepoForge" in result.output
        assert "skills" in result.output
        assert "score" in result.output
        assert "scan" in result.output
        assert "docs" in result.output
        assert "export" in result.output
        assert "compress" in result.output
        assert "graph" in result.output

    def test_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output

    def test_skills_help(self, runner):
        result = runner.invoke(main, ["skills", "--help"])
        assert result.exit_code == 0
        assert "SKILL.md" in result.output
        assert "--model" in result.output
        assert "--compress" in result.output
        assert "--targets" in result.output

    def test_docs_help(self, runner):
        result = runner.invoke(main, ["docs", "--help"])
        assert result.exit_code == 0
        assert "documentation" in result.output.lower()
        assert "--lang" in result.output

    def test_export_help(self, runner):
        result = runner.invoke(main, ["export", "--help"])
        assert result.exit_code == 0
        assert "Flatten" in result.output

    def test_score_help(self, runner):
        result = runner.invoke(main, ["score", "--help"])
        assert result.exit_code == 0
        assert "Score" in result.output

    def test_scan_help(self, runner):
        result = runner.invoke(main, ["scan", "--help"])
        assert result.exit_code == 0
        assert "Security" in result.output

    def test_compress_help(self, runner):
        result = runner.invoke(main, ["compress", "--help"])
        assert result.exit_code == 0
        assert "Token-optimize" in result.output

    def test_graph_help(self, runner):
        result = runner.invoke(main, ["graph", "--help"])
        assert result.exit_code == 0
        assert "knowledge graph" in result.output.lower()


# ---------------------------------------------------------------------------
# export subcommand
# ---------------------------------------------------------------------------

class TestExportCommand:
    def test_export_stdout(self, runner, sample_repo):
        result = runner.invoke(main, ["export", "-w", str(sample_repo), "-q"])
        assert result.exit_code == 0
        assert "main.py" in result.output or "sample-project" in result.output.lower()

    def test_export_to_file(self, runner, sample_repo):
        out_file = sample_repo / "context.md"
        result = runner.invoke(main, [
            "export", "-w", str(sample_repo),
            "-o", str(out_file), "-q",
        ])
        assert result.exit_code == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert len(content) > 100

    def test_export_xml_format(self, runner, sample_repo):
        result = runner.invoke(main, [
            "export", "-w", str(sample_repo),
            "--format", "xml", "-q",
        ])
        assert result.exit_code == 0
        assert "<" in result.output

    def test_export_no_contents(self, runner, sample_repo):
        result = runner.invoke(main, [
            "export", "-w", str(sample_repo),
            "--no-contents", "-q",
        ])
        assert result.exit_code == 0

    def test_export_max_tokens(self, runner, sample_repo):
        result = runner.invoke(main, [
            "export", "-w", str(sample_repo),
            "--max-tokens", "500", "-q",
        ])
        assert result.exit_code == 0

    def test_export_invalid_dir(self, runner, tmp_path):
        result = runner.invoke(main, [
            "export", "-w", str(tmp_path / "nonexistent"),
        ])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# score subcommand
# ---------------------------------------------------------------------------

class TestScoreCommand:
    def test_score_table(self, runner, sample_skill):
        result = runner.invoke(main, [
            "score", "-w", str(sample_skill), "-q",
        ])
        assert result.exit_code == 0
        assert "backend-skill" in result.output or "SKILL" in result.output

    def test_score_json(self, runner, sample_skill):
        result = runner.invoke(main, [
            "score", "-w", str(sample_skill),
            "--format", "json", "-q",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_score_markdown(self, runner, sample_skill):
        result = runner.invoke(main, [
            "score", "-w", str(sample_skill),
            "--format", "markdown", "-q",
        ])
        assert result.exit_code == 0

    def test_score_min_score_pass(self, runner, sample_skill):
        result = runner.invoke(main, [
            "score", "-w", str(sample_skill),
            "--min-score", "0.1", "-q",
        ])
        assert result.exit_code == 0

    def test_score_min_score_fail(self, runner, sample_skill):
        result = runner.invoke(main, [
            "score", "-w", str(sample_skill),
            "--min-score", "0.99", "-q",
        ])
        assert result.exit_code == 1

    def test_score_no_skills_dir(self, runner, tmp_path):
        result = runner.invoke(main, [
            "score", "-w", str(tmp_path), "-q",
        ])
        assert result.exit_code == 1

    def test_score_custom_skills_dir(self, runner, sample_skill):
        skills_dir = sample_skill / ".claude" / "skills"
        result = runner.invoke(main, [
            "score", "-d", str(skills_dir), "-q",
        ])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# scan subcommand
# ---------------------------------------------------------------------------

class TestScanCommand:
    def test_scan_clean_repo(self, runner, sample_skill):
        result = runner.invoke(main, [
            "scan", "-w", str(sample_skill), "-q",
        ])
        assert result.exit_code == 0

    def test_scan_table_format(self, runner, sample_skill):
        result = runner.invoke(main, [
            "scan", "-w", str(sample_skill),
            "--format", "table", "-q",
        ])
        assert result.exit_code == 0

    def test_scan_json_format(self, runner, sample_skill):
        result = runner.invoke(main, [
            "scan", "-w", str(sample_skill),
            "--format", "json", "-q",
        ])
        assert result.exit_code == 0

    def test_scan_target_dir(self, runner, sample_skill):
        target = sample_skill / ".claude" / "skills"
        result = runner.invoke(main, [
            "scan", "--target-dir", str(target), "-q",
        ])
        assert result.exit_code == 0

    def test_scan_fail_on_critical_clean(self, runner, sample_skill):
        result = runner.invoke(main, [
            "scan", "-w", str(sample_skill),
            "--fail-on", "critical", "-q",
        ])
        assert result.exit_code == 0

    def test_scan_with_allowlist(self, runner, sample_skill):
        result = runner.invoke(main, [
            "scan", "-w", str(sample_skill),
            "--allowlist", "SEC-020,SEC-022", "-q",
        ])
        assert result.exit_code == 0

    def test_scan_nonexistent_target(self, runner, tmp_path):
        result = runner.invoke(main, [
            "scan", "--target-dir", str(tmp_path / "nope"),
        ])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# compress subcommand
# ---------------------------------------------------------------------------

class TestCompressCommand:
    def test_compress_dry_run(self, runner, sample_skill):
        target = sample_skill / ".claude" / "skills"
        result = runner.invoke(main, [
            "compress", "-w", str(sample_skill),
            "--target-dir", str(target),
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0

    def test_compress_normal(self, runner, sample_skill):
        target = sample_skill / ".claude" / "skills"
        result = runner.invoke(main, [
            "compress", "--target-dir", str(target), "-q",
        ])
        assert result.exit_code == 0

    def test_compress_aggressive(self, runner, sample_skill):
        target = sample_skill / ".claude" / "skills"
        result = runner.invoke(main, [
            "compress", "--target-dir", str(target),
            "--aggressive", "-q",
        ])
        assert result.exit_code == 0

    def test_compress_no_dir(self, runner, tmp_path):
        result = runner.invoke(main, [
            "compress", "-w", str(tmp_path), "-q",
        ])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# graph subcommand
# ---------------------------------------------------------------------------

class TestGraphCommand:
    def test_graph_summary(self, runner, sample_repo):
        result = runner.invoke(main, [
            "graph", "-w", str(sample_repo), "-q",
        ])
        assert result.exit_code == 0

    def test_graph_mermaid(self, runner, sample_repo):
        result = runner.invoke(main, [
            "graph", "-w", str(sample_repo),
            "--format", "mermaid", "-q",
        ])
        assert result.exit_code == 0

    def test_graph_json(self, runner, sample_repo):
        result = runner.invoke(main, [
            "graph", "-w", str(sample_repo),
            "--format", "json", "-q",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "nodes" in data
        assert "edges" in data

    def test_graph_dot(self, runner, sample_repo):
        result = runner.invoke(main, [
            "graph", "-w", str(sample_repo),
            "--format", "dot", "-q",
        ])
        assert result.exit_code == 0
        assert "digraph" in result.output

    def test_graph_to_file(self, runner, sample_repo):
        out_file = sample_repo / "graph.json"
        result = runner.invoke(main, [
            "graph", "-w", str(sample_repo),
            "--format", "json",
            "-o", str(out_file), "-q",
        ])
        assert result.exit_code == 0
        assert out_file.exists()


# ---------------------------------------------------------------------------
# graph subcommand (v2 — extractor-based)
# ---------------------------------------------------------------------------

class TestGraphV2Command:
    def test_graph_v2_summary(self, runner, sample_repo):
        """--v2 should produce a summary with Modules and Dependencies."""
        result = runner.invoke(main, [
            "graph", "-w", str(sample_repo), "--v2", "-q",
        ])
        assert result.exit_code == 0
        assert "Modules:" in result.output

    def test_graph_v2_mermaid(self, runner, sample_repo):
        """--v2 --format mermaid should produce valid Mermaid output."""
        result = runner.invoke(main, [
            "graph", "-w", str(sample_repo),
            "--v2", "--format", "mermaid", "-q",
        ])
        assert result.exit_code == 0
        assert "graph LR" in result.output

    def test_graph_v2_json(self, runner, sample_repo):
        """--v2 --format json should produce valid JSON with nodes+edges."""
        result = runner.invoke(main, [
            "graph", "-w", str(sample_repo),
            "--v2", "--format", "json", "-q",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_graph_v2_dot(self, runner, sample_repo):
        """--v2 --format dot should produce valid DOT output."""
        result = runner.invoke(main, [
            "graph", "-w", str(sample_repo),
            "--v2", "--format", "dot", "-q",
        ])
        assert result.exit_code == 0
        assert "digraph" in result.output

    def test_graph_v2_blast_radius(self, runner, sample_repo):
        """--v2 --blast-radius should show blast radius with v2 details."""
        # First get a valid file path from the v2 graph
        result = runner.invoke(main, [
            "graph", "-w", str(sample_repo),
            "--v2", "--format", "json", "-q",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        if data["nodes"]:
            node_id = data["nodes"][0]["id"]
            result = runner.invoke(main, [
                "graph", "-w", str(sample_repo),
                "--v2", "--blast-radius", node_id, "-q",
            ])
            assert result.exit_code == 0
            assert "Blast radius for:" in result.output
            assert "Affected files:" in result.output or "Max depth reached:" in result.output

    def test_graph_v2_depth_flag(self, runner, sample_repo):
        """--v2 --depth should be accepted and work."""
        result = runner.invoke(main, [
            "graph", "-w", str(sample_repo),
            "--v2", "--depth", "1", "-q",
        ])
        assert result.exit_code == 0

    def test_graph_v2_json_valid_structure(self, runner, sample_repo):
        """v2 JSON nodes should have expected fields."""
        result = runner.invoke(main, [
            "graph", "-w", str(sample_repo),
            "--v2", "--format", "json", "-q",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        if data["nodes"]:
            node = data["nodes"][0]
            assert "id" in node
            assert "name" in node
            assert "type" in node
            assert "file_path" in node
            assert "exports" in node

    def test_graph_v2_to_file(self, runner, sample_repo):
        """v2 output should be writable to a file."""
        out_file = sample_repo / "graph_v2.json"
        result = runner.invoke(main, [
            "graph", "-w", str(sample_repo),
            "--v2", "--format", "json",
            "-o", str(out_file), "-q",
        ])
        assert result.exit_code == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert "nodes" in data


# ---------------------------------------------------------------------------
# skills subcommand (dry-run only — no LLM)
# ---------------------------------------------------------------------------

class TestSkillsCommand:
    def test_skills_dry_run(self, runner, sample_repo):
        result = runner.invoke(main, [
            "skills", "-w", str(sample_repo),
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0

    def test_skills_dry_run_with_options(self, runner, sample_repo):
        result = runner.invoke(main, [
            "skills", "-w", str(sample_repo),
            "--dry-run", "--no-opencode",
            "--complexity", "small",
            "-q",
        ])
        assert result.exit_code == 0

    def test_skills_dry_run_no_files_written(self, runner, sample_repo):
        """Dry-run must NOT create any files or call the LLM."""
        output_dir = sample_repo / ".claude"
        opencode_dir = sample_repo / ".opencode"
        atl_dir = sample_repo / ".atl"

        # Ensure output dirs don't exist before the run
        assert not output_dir.exists()
        assert not opencode_dir.exists()
        assert not atl_dir.exists()

        with patch("repoforge.generator.build_llm") as mock_build_llm:
            result = runner.invoke(main, [
                "skills", "-w", str(sample_repo),
                "--dry-run", "--no-opencode",
            ])

        assert result.exit_code == 0
        # build_llm must NOT have been called
        mock_build_llm.assert_not_called()
        # No output directories should have been created
        assert not output_dir.exists(), ".claude/ should not exist after dry-run"
        assert not opencode_dir.exists(), ".opencode/ should not exist after dry-run"
        assert not atl_dir.exists(), ".atl/ should not exist after dry-run"

    def test_skills_invalid_dir(self, runner, tmp_path):
        result = runner.invoke(main, [
            "skills", "-w", str(tmp_path / "nonexistent"),
        ])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# docs subcommand (dry-run only — no LLM)
# ---------------------------------------------------------------------------

class TestDocsCommand:
    def test_docs_dry_run(self, runner, sample_repo):
        result = runner.invoke(main, [
            "docs", "-w", str(sample_repo),
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0

    def test_docs_dry_run_with_language(self, runner, sample_repo):
        result = runner.invoke(main, [
            "docs", "-w", str(sample_repo),
            "--dry-run", "--lang", "Spanish", "-q",
        ])
        assert result.exit_code == 0

    def test_docs_invalid_dir(self, runner, tmp_path):
        result = runner.invoke(main, [
            "docs", "-w", str(tmp_path / "nonexistent"),
        ])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Error handling & edge cases
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_unknown_command(self, runner):
        result = runner.invoke(main, ["nonexistent"])
        assert result.exit_code != 0

    def test_h_flag_works_like_help(self, runner):
        result = runner.invoke(main, ["-h"])
        assert result.exit_code == 0
        assert "RepoForge" in result.output

    def test_export_verbose_mode(self, runner, sample_repo):
        """Verbose mode should print progress to stderr."""
        result = runner.invoke(main, [
            "export", "-w", str(sample_repo),
        ])
        assert result.exit_code == 0
