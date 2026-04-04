"""
tests/test_checker.py — Tests for code reference checking in generated docs.

Tests cover:
- File path reference detection
- Symbol reference detection
- Validation against file index (valid, broken)
- Report formats (table, json, markdown)
- CLI check subcommand
- Edge cases (empty docs, no refs, fenced code blocks)
- CheckResult properties
- check_docs convenience function
"""

import json
from pathlib import Path

import pytest

from repoforge.checker import (
    CheckResult,
    CodeRef,
    ReferenceChecker,
    RefStatus,
    RefType,
    check_docs,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_repo(tmp_path):
    """Create a minimal repo with source files and docs."""
    # Source files
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.py").write_text(
        'def validate_token(token: str) -> bool:\n    return True\n'
    )
    (tmp_path / "src" / "models.py").write_text(
        'class UserModel:\n    pass\n'
    )
    (tmp_path / "src" / "utils.py").write_text(
        'def format_date(dt):\n    return str(dt)\n'
    )
    (tmp_path / "config.yaml").write_text("key: value\n")

    # Docs directory
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "01-overview.md").write_text(
        "# Overview\n\n"
        "The auth module is at `src/auth.py` and handles token validation.\n"
        "Configuration is in `config.yaml`.\n"
        "The deleted file was at `src/deleted.ts`.\n"
    )
    (docs / "02-architecture.md").write_text(
        "# Architecture\n\n"
        "Models are defined in `src/models.py`.\n"
        "The `UserModel` class handles user data.\n"
        "See `src/nonexistent.go` for details.\n"
    )

    return tmp_path


@pytest.fixture
def repo_with_fenced_blocks(tmp_path):
    """Repo with docs containing fenced code blocks."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def main(): pass\n")

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text(
        "# Guide\n\n"
        "The entry point is `src/app.py`.\n\n"
        "```python\n"
        "# This should be ignored: `src/fake.py`\n"
        "import src.fake_module\n"
        "```\n\n"
        "After the code block, `src/missing.ts` is referenced.\n"
    )

    return tmp_path


@pytest.fixture
def empty_docs_repo(tmp_path):
    """Repo with empty docs directory."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "empty.md").write_text("# Empty\n\nNo code references here.\n")
    return tmp_path


# ---------------------------------------------------------------------------
# Reference detection tests
# ---------------------------------------------------------------------------

class TestReferenceExtraction:
    """Tests for extracting code references from markdown content."""

    def test_detects_file_path_refs(self, sample_repo):
        checker = ReferenceChecker(sample_repo)
        refs = checker.scan_content(
            "Check `src/auth.py` for details.",
            "test.md",
        )
        file_refs = [r for r in refs if r.ref_type == RefType.FILE]
        assert len(file_refs) >= 1
        assert any(r.ref_text == "src/auth.py" for r in file_refs)

    def test_detects_multiple_refs_per_line(self, sample_repo):
        checker = ReferenceChecker(sample_repo)
        refs = checker.scan_content(
            "See `src/auth.py` and `src/models.py` for implementation.",
            "test.md",
        )
        file_refs = [r for r in refs if r.ref_type == RefType.FILE]
        assert len(file_refs) >= 2

    def test_skips_fenced_code_blocks(self, repo_with_fenced_blocks):
        checker = ReferenceChecker(repo_with_fenced_blocks)
        docs_dir = repo_with_fenced_blocks / "docs"
        result = checker.scan_directory(docs_dir)

        # src/app.py should be found (outside fence)
        # src/fake.py should NOT be found (inside fence)
        ref_texts = [r.ref_text for r in result.refs]
        assert "src/app.py" in ref_texts
        assert "src/fake.py" not in ref_texts

    def test_ignores_common_keywords(self, sample_repo):
        checker = ReferenceChecker(sample_repo)
        refs = checker.scan_content(
            "Use `true` and `false` values. Also `null`.",
            "test.md",
        )
        assert len(refs) == 0


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestValidation:
    """Tests for validating references against the codebase."""

    def test_valid_file_ref(self, sample_repo):
        checker = ReferenceChecker(sample_repo)
        refs = checker.scan_content(
            "The file `src/auth.py` exists.",
            "test.md",
        )
        file_refs = [r for r in refs if r.ref_text == "src/auth.py"]
        assert len(file_refs) == 1
        assert file_refs[0].status == RefStatus.VALID

    def test_broken_file_ref(self, sample_repo):
        checker = ReferenceChecker(sample_repo)
        refs = checker.scan_content(
            "The file `src/deleted.ts` was removed.",
            "test.md",
        )
        file_refs = [r for r in refs if r.ref_text == "src/deleted.ts"]
        assert len(file_refs) == 1
        assert file_refs[0].status == RefStatus.BROKEN

    def test_valid_config_file_ref(self, sample_repo):
        checker = ReferenceChecker(sample_repo)
        refs = checker.scan_content(
            "See `config.yaml` for settings.",
            "test.md",
        )
        yaml_refs = [r for r in refs if r.ref_text == "config.yaml"]
        assert len(yaml_refs) == 1
        assert yaml_refs[0].status == RefStatus.VALID

    def test_directory_scan(self, sample_repo):
        checker = ReferenceChecker(sample_repo)
        result = checker.scan_directory(sample_repo / "docs")

        assert result.files_scanned == 2
        assert result.total_count > 0
        assert result.valid_count > 0
        assert result.broken_count > 0


# ---------------------------------------------------------------------------
# CheckResult properties tests
# ---------------------------------------------------------------------------

class TestCheckResult:
    """Tests for CheckResult dataclass properties."""

    def test_empty_result(self):
        result = CheckResult(files_scanned=0)
        assert result.total_count == 0
        assert result.valid_count == 0
        assert result.broken_count == 0
        assert result.unresolvable_count == 0

    def test_counts(self):
        refs = [
            CodeRef("a.py", RefType.FILE, RefStatus.VALID, "doc.md", 1, "a.py"),
            CodeRef("b.py", RefType.FILE, RefStatus.BROKEN, "doc.md", 2),
            CodeRef("c.py", RefType.FILE, RefStatus.VALID, "doc.md", 3, "c.py"),
            CodeRef("Foo.bar", RefType.SYMBOL, RefStatus.UNRESOLVABLE, "doc.md", 4),
        ]
        result = CheckResult(files_scanned=1, refs=refs)
        assert result.total_count == 4
        assert result.valid_count == 2
        assert result.broken_count == 1
        assert result.unresolvable_count == 1


# ---------------------------------------------------------------------------
# Report format tests
# ---------------------------------------------------------------------------

class TestReporting:
    """Tests for report output formats."""

    def _make_result(self):
        refs = [
            CodeRef("src/auth.py", RefType.FILE, RefStatus.VALID, "docs/01.md", 5, "src/auth.py"),
            CodeRef("src/deleted.ts", RefType.FILE, RefStatus.BROKEN, "docs/01.md", 7),
            CodeRef("Foo.bar", RefType.SYMBOL, RefStatus.UNRESOLVABLE, "docs/02.md", 3),
        ]
        return CheckResult(files_scanned=2, refs=refs)

    def test_table_format(self):
        result = self._make_result()
        report = ReferenceChecker.report(result, fmt="table")
        assert "Files scanned: 2" in report
        assert "src/deleted.ts" in report
        assert "BROKEN REFERENCES:" in report

    def test_json_format(self):
        result = self._make_result()
        report = ReferenceChecker.report(result, fmt="json")
        data = json.loads(report)
        assert data["files_scanned"] == 2
        assert data["summary"]["broken"] == 1
        assert data["summary"]["valid"] == 1
        assert len(data["refs"]) == 3

    def test_markdown_format(self):
        result = self._make_result()
        report = ReferenceChecker.report(result, fmt="markdown")
        assert "## Reference Check Report" in report
        assert "Broken References" in report
        assert "`src/deleted.ts`" in report

    def test_all_valid_report(self):
        refs = [
            CodeRef("src/auth.py", RefType.FILE, RefStatus.VALID, "doc.md", 1, "src/auth.py"),
        ]
        result = CheckResult(files_scanned=1, refs=refs)
        report = ReferenceChecker.report(result, fmt="table")
        assert "All references are valid" in report


# ---------------------------------------------------------------------------
# Empty / edge case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_docs_no_refs(self, empty_docs_repo):
        checker = ReferenceChecker(empty_docs_repo)
        result = checker.scan_directory(empty_docs_repo / "docs")
        assert result.files_scanned == 1
        assert result.total_count == 0

    def test_nonexistent_docs_dir(self, tmp_path):
        checker = ReferenceChecker(tmp_path)
        result = checker.scan_directory(tmp_path / "nonexistent")
        assert result.files_scanned == 0

    def test_empty_content(self, tmp_path):
        checker = ReferenceChecker(tmp_path)
        refs = checker.scan_content("", "test.md")
        assert refs == []


# ---------------------------------------------------------------------------
# Convenience function tests
# ---------------------------------------------------------------------------

class TestCheckDocs:
    """Tests for the check_docs convenience function."""

    def test_check_docs_returns_result(self, sample_repo):
        result = check_docs(str(sample_repo), docs_dir="docs")
        assert isinstance(result, CheckResult)
        assert result.files_scanned > 0

    def test_check_docs_missing_dir(self, tmp_path):
        result = check_docs(str(tmp_path), docs_dir="nonexistent")
        assert result.files_scanned == 0


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------

class TestCLIIntegration:
    """Tests for the CLI check subcommand."""

    def test_check_command_exists(self):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["check", "--help"])
        assert result.exit_code == 0
        assert "Validate code references" in result.output

    def test_check_missing_docs_dir(self, tmp_path):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["check", "-w", str(tmp_path)])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_check_with_docs(self, sample_repo):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["check", "-w", str(sample_repo), "--docs-dir", "docs"])
        assert result.exit_code == 0
        assert "References:" in result.output or "Files scanned:" in result.output

    def test_check_fail_on_broken(self, sample_repo):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "check", "-w", str(sample_repo),
            "--docs-dir", "docs",
            "--fail-on", "broken",
        ])
        # sample_repo has broken refs (src/deleted.ts, src/nonexistent.go)
        assert result.exit_code == 1

    def test_check_json_output(self, sample_repo):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "check", "-w", str(sample_repo),
            "--docs-dir", "docs",
            "--format", "json",
            "-q",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "summary" in data
        assert "refs" in data


# ---------------------------------------------------------------------------
# Wikilink reference tests
# ---------------------------------------------------------------------------

@pytest.fixture
def wikilink_repo(tmp_path):
    """Create a repo with source files and docs using wikilinks."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.py").write_text(
        'def validate_token(token: str) -> bool:\n    return True\n'
    )
    (tmp_path / "src" / "models.py").write_text(
        'class UserModel:\n    pass\n'
    )

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "01-overview.md").write_text(
        "# Overview\n\n"
        "The auth module is at [[src/auth.py]] and handles token validation.\n"
        "The validate function is at [[src/auth.py#validate_token]].\n"
        "A broken link: [[src/deleted.py]].\n"
    )
    (docs / "02-mixed.md").write_text(
        "# Mixed\n\n"
        "Backtick ref: `src/models.py` and wikilink: [[src/auth.py]].\n"
        "```python\n"
        "# This wikilink inside fenced block should be ignored: [[src/fake.py]]\n"
        "```\n"
    )
    return tmp_path


class TestWikilinkExtraction:
    """Tests for wikilink reference extraction."""

    def test_detects_simple_wikilink(self, wikilink_repo):
        checker = ReferenceChecker(wikilink_repo)
        refs = checker.scan_content(
            "See [[src/auth.py]] for details.",
            "test.md",
        )
        wiki_refs = [r for r in refs if r.ref_type == RefType.WIKILINK]
        assert len(wiki_refs) == 1
        assert wiki_refs[0].ref_text == "src/auth.py"

    def test_detects_wikilink_with_anchor(self, wikilink_repo):
        checker = ReferenceChecker(wikilink_repo)
        refs = checker.scan_content(
            "See [[src/auth.py#validate_token]] for the function.",
            "test.md",
        )
        wiki_refs = [r for r in refs if r.ref_type == RefType.WIKILINK]
        assert len(wiki_refs) == 1
        assert wiki_refs[0].ref_text == "src/auth.py#validate_token"

    def test_detects_multiple_wikilinks(self, wikilink_repo):
        checker = ReferenceChecker(wikilink_repo)
        refs = checker.scan_content(
            "See [[src/auth.py]] and [[src/models.py]] for implementation.",
            "test.md",
        )
        wiki_refs = [r for r in refs if r.ref_type == RefType.WIKILINK]
        assert len(wiki_refs) == 2

    def test_skips_wikilinks_in_fenced_blocks(self, wikilink_repo):
        checker = ReferenceChecker(wikilink_repo)
        refs = checker.scan_content(
            "Normal: [[src/auth.py]]\n\n```\n[[src/fake.py]]\n```\n\nAfter.",
            "test.md",
        )
        wiki_refs = [r for r in refs if r.ref_type == RefType.WIKILINK]
        texts = [r.ref_text for r in wiki_refs]
        assert "src/auth.py" in texts
        assert "src/fake.py" not in texts


class TestWikilinkValidation:
    """Tests for wikilink reference validation."""

    def test_valid_file_wikilink(self, wikilink_repo):
        checker = ReferenceChecker(wikilink_repo)
        refs = checker.scan_content(
            "The module [[src/auth.py]] handles auth.",
            "test.md",
        )
        wiki_refs = [r for r in refs if r.ref_type == RefType.WIKILINK]
        assert len(wiki_refs) == 1
        assert wiki_refs[0].status == RefStatus.VALID

    def test_broken_file_wikilink(self, wikilink_repo):
        checker = ReferenceChecker(wikilink_repo)
        refs = checker.scan_content(
            "The file [[src/deleted.py]] was removed.",
            "test.md",
        )
        wiki_refs = [r for r in refs if r.ref_type == RefType.WIKILINK]
        assert len(wiki_refs) == 1
        assert wiki_refs[0].status == RefStatus.BROKEN

    def test_wikilink_with_valid_anchor(self, wikilink_repo):
        checker = ReferenceChecker(wikilink_repo)
        refs = checker.scan_content(
            "See [[src/auth.py#validate_token]] for validation.",
            "test.md",
        )
        wiki_refs = [r for r in refs if r.ref_type == RefType.WIKILINK]
        assert len(wiki_refs) == 1
        assert wiki_refs[0].status == RefStatus.VALID

    def test_directory_scan_with_wikilinks(self, wikilink_repo):
        checker = ReferenceChecker(wikilink_repo)
        result = checker.scan_directory(wikilink_repo / "docs")
        wiki_refs = [r for r in result.refs if r.ref_type == RefType.WIKILINK]
        assert len(wiki_refs) > 0
        valid_wiki = [r for r in wiki_refs if r.status == RefStatus.VALID]
        broken_wiki = [r for r in wiki_refs if r.status == RefStatus.BROKEN]
        assert len(valid_wiki) > 0
        assert len(broken_wiki) > 0

    def test_wikilink_coexists_with_backtick_refs(self, wikilink_repo):
        """Wikilinks and backtick refs should both be detected in the same doc."""
        checker = ReferenceChecker(wikilink_repo)
        result = checker.scan_directory(wikilink_repo / "docs")
        types = {r.ref_type for r in result.refs}
        assert RefType.WIKILINK in types
        assert RefType.FILE in types

    def test_wikilink_in_report_json(self, wikilink_repo):
        checker = ReferenceChecker(wikilink_repo)
        result = checker.scan_directory(wikilink_repo / "docs")
        report = ReferenceChecker.report(result, fmt="json")
        data = json.loads(report)
        wikilink_refs = [r for r in data["refs"] if r["ref_type"] == "wikilink"]
        assert len(wikilink_refs) > 0
