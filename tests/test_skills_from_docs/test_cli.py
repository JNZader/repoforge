"""Tests for skills-from-docs CLI subcommand."""

import pytest
from pathlib import Path
from click.testing import CliRunner

from repoforge.cli import main


@pytest.fixture
def docs_dir(tmp_path):
    """Create a temp dir with sample markdown docs."""
    (tmp_path / "README.md").write_text(
        "# Sample Library\n\n"
        "A great library for doing things.\n\n"
        "## Installation\n\n"
        "```bash\npip install sample-lib\n```\n\n"
        "## Usage\n\n"
        "```python\nimport sample_lib\nsample_lib.do_thing()\n```\n\n"
        "## Best Practices\n\n"
        "- You should always validate input\n"
        "- Prefer async operations for I/O\n"
        "- Don't use global state\n"
    )
    (tmp_path / "api.md").write_text(
        "# API Reference\n\n"
        "## do_thing()\n\n"
        "Does the thing.\n\n"
        "```python\nresult = sample_lib.do_thing(param='value')\n```\n"
    )
    return tmp_path


class TestSkillsFromDocsCli:
    def test_dry_run(self, docs_dir):
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills-from-docs",
            "-w", str(docs_dir),
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "---" in result.output  # YAML frontmatter
        assert "name:" in result.output

    def test_generates_skill_file(self, docs_dir, tmp_path):
        output_dir = tmp_path / "output"
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills-from-docs",
            "-w", str(docs_dir),
            "-o", str(output_dir),
            "--no-check-conflicts",
        ])
        assert result.exit_code == 0
        # Should have created a SKILL.md somewhere under output_dir
        skill_files = list(output_dir.rglob("SKILL.md"))
        assert len(skill_files) == 1
        content = skill_files[0].read_text()
        assert "---" in content
        assert "name:" in content

    def test_custom_name(self, docs_dir, tmp_path):
        output_dir = tmp_path / "output"
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills-from-docs",
            "-w", str(docs_dir),
            "-o", str(output_dir),
            "--name", "my-custom-skill",
            "--no-check-conflicts",
        ])
        assert result.exit_code == 0
        skill_file = output_dir / "my-custom-skill" / "SKILL.md"
        assert skill_file.exists()
        content = skill_file.read_text()
        assert "name: my-custom-skill" in content

    def test_quiet_mode(self, docs_dir, tmp_path):
        output_dir = tmp_path / "output"
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills-from-docs",
            "-w", str(docs_dir),
            "-o", str(output_dir),
            "--no-check-conflicts",
            "-q",
        ])
        assert result.exit_code == 0

    def test_invalid_source(self):
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills-from-docs",
            "-w", "/nonexistent/path/12345",
        ])
        assert result.exit_code != 0

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["skills-from-docs", "--help"])
        assert result.exit_code == 0
        assert "Generate SKILL.md from documentation" in result.output
        assert "--dry-run" in result.output
        assert "--name" in result.output
