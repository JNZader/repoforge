"""
tests/test_skill_validator.py — Tests for SKILL.md format validation.

Tests cover:
- Frontmatter detection and required key validation
- Required section checks (## Critical Rules)
- File size limit enforcement
- Forbidden syntax detection (Templater, raw HTML)
- Strict mode (## Examples requirement)
- Directory scanning with skill-candidate filtering
- Report formats (text, json)
- CLI validate-skills command
- Exit code behaviour (--fail-on error/warning)
- Edge cases (unreadable files, no skills found, single-file target)
"""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from repoforge.cli import main
from repoforge.skill_validator import (
    FileResult,
    SkillValidator,
    ValidationResult,
    Violation,
    ViolationLevel,
    validate_skill,
)

# ---------------------------------------------------------------------------
# Content fixtures
# ---------------------------------------------------------------------------

VALID_SKILL = """\
---
name: my-skill
description: >
  A valid skill for testing.
version: "1.0"
---

## Critical Rules

1. Always follow the patterns.
2. Never skip validation.

## Examples

```python
def example():
    return True
```
"""

SKILL_MISSING_FRONTMATTER = """\
## Critical Rules

1. Always follow the patterns.
"""

SKILL_MISSING_NAME = """\
---
description: >
  A skill without a name key.
version: "1.0"
---

## Critical Rules

1. Rule one.
"""

SKILL_MISSING_DESCRIPTION = """\
---
name: no-desc-skill
version: "1.0"
---

## Critical Rules

1. Rule one.
"""

SKILL_MISSING_VERSION = """\
---
name: no-version-skill
description: A skill without a version.
---

## Critical Rules

1. Rule one.
"""

SKILL_MISSING_CRITICAL_RULES = """\
---
name: no-rules-skill
description: A skill without Critical Rules section.
version: "1.0"
---

## Patterns

Some patterns here.
"""

SKILL_WITH_TEMPLATER = """\
---
name: templater-skill
description: A skill with Templater syntax.
version: "1.0"
---

## Critical Rules

1. Use <% tp.date.now() %> somewhere.
"""

SKILL_WITH_RAW_HTML = """\
---
name: html-skill
description: A skill with raw HTML.
version: "1.0"
---

## Critical Rules

1. Use <strong>bold</strong> formatting.
"""

SKILL_UNCLOSED_FRONTMATTER = """\
---
name: unclosed
description: No closing ---.
version: "1.0"

## Critical Rules

1. Rule one.
"""


def make_long_skill(lines: int) -> str:
    """Generate a valid SKILL.md with many lines."""
    content = VALID_SKILL
    padding = "\n".join(f"- Rule {i}" for i in range(lines))
    return content + "\n" + padding


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def skills_dir(tmp_path):
    """Create a temp directory with a mix of valid and invalid SKILL.md files."""
    skills = tmp_path / "skills"
    skills.mkdir()

    # Valid skill
    (skills / "valid").mkdir()
    (skills / "valid" / "SKILL.md").write_text(VALID_SKILL, encoding="utf-8")

    # Skill with missing name
    (skills / "no-name").mkdir()
    (skills / "no-name" / "SKILL.md").write_text(SKILL_MISSING_NAME, encoding="utf-8")

    # Skill missing version key (has name: so it's a candidate, but version is absent)
    (skills / "no-version").mkdir()
    (skills / "no-version" / "SKILL.md").write_text("""\
---
name: no-version-skill
description: Missing version key.
---

## Critical Rules

1. Rule one.
""", encoding="utf-8")

    # Not a skill (no frontmatter) — should be ignored
    (skills / "README.md").write_text("# Just a README\n\nNot a skill.\n", encoding="utf-8")

    return skills


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# Unit: frontmatter validation
# ---------------------------------------------------------------------------


class TestFrontmatterValidation:

    def test_valid_frontmatter_passes(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        result = validate_skill(f)
        fm_errors = [v for v in result.violations if "frontmatter" in v.rule]
        assert fm_errors == [], f"Expected no frontmatter errors, got: {fm_errors}"

    def test_missing_frontmatter_raises_error(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(SKILL_MISSING_FRONTMATTER, encoding="utf-8")
        result = validate_skill(f)
        assert any(v.rule == "frontmatter-missing" for v in result.violations)
        assert not result.passed

    def test_unclosed_frontmatter_raises_error(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(SKILL_UNCLOSED_FRONTMATTER, encoding="utf-8")
        result = validate_skill(f)
        assert any("frontmatter" in v.rule for v in result.violations)
        assert not result.passed

    def test_missing_name_key(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(SKILL_MISSING_NAME, encoding="utf-8")
        result = validate_skill(f)
        assert any(v.rule == "frontmatter-missing-name" for v in result.violations)

    def test_missing_description_key(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(SKILL_MISSING_DESCRIPTION, encoding="utf-8")
        result = validate_skill(f)
        assert any(v.rule == "frontmatter-missing-description" for v in result.violations)

    def test_missing_version_key(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(SKILL_MISSING_VERSION, encoding="utf-8")
        result = validate_skill(f)
        assert any(v.rule == "frontmatter-missing-version" for v in result.violations)

    def test_all_required_keys_present(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        result = validate_skill(f)
        fm_key_errors = [v for v in result.violations if v.rule.startswith("frontmatter-missing-")]
        assert fm_key_errors == []


# ---------------------------------------------------------------------------
# Unit: section validation
# ---------------------------------------------------------------------------


class TestSectionValidation:

    def test_critical_rules_required(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(SKILL_MISSING_CRITICAL_RULES, encoding="utf-8")
        result = validate_skill(f)
        assert any(v.rule == "section-missing" for v in result.violations)
        assert not result.passed

    def test_valid_skill_has_critical_rules(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        result = validate_skill(f)
        section_errors = [v for v in result.violations if v.rule == "section-missing"]
        assert section_errors == []

    def test_strict_mode_requires_examples(self, tmp_path):
        # Skill with Critical Rules but no Examples
        skill_no_examples = """\
---
name: no-examples
description: A skill without Examples section.
version: "1.0"
---

## Critical Rules

1. Rule one.
"""
        f = tmp_path / "SKILL.md"
        f.write_text(skill_no_examples, encoding="utf-8")
        result = validate_skill(f, strict=True)
        assert any(v.rule == "section-missing-strict" for v in result.violations)
        assert any(v.level == ViolationLevel.WARNING for v in result.violations)

    def test_strict_mode_examples_present_passes(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        result = validate_skill(f, strict=True)
        strict_warnings = [v for v in result.violations if v.rule == "section-missing-strict"]
        assert strict_warnings == []

    def test_non_strict_missing_examples_passes(self, tmp_path):
        skill_no_examples = """\
---
name: no-examples
description: A skill without Examples section.
version: "1.0"
---

## Critical Rules

1. Rule one.
"""
        f = tmp_path / "SKILL.md"
        f.write_text(skill_no_examples, encoding="utf-8")
        result = validate_skill(f, strict=False)
        strict_violations = [v for v in result.violations if "strict" in v.rule]
        assert strict_violations == []


# ---------------------------------------------------------------------------
# Unit: file size limit
# ---------------------------------------------------------------------------


class TestFileSizeLimit:

    def test_within_limit_passes(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        result = validate_skill(f, max_lines=400)
        size_warnings = [v for v in result.violations if v.rule == "file-too-long"]
        assert size_warnings == []

    def test_exceeds_limit_warning(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(make_long_skill(500), encoding="utf-8")
        result = validate_skill(f, max_lines=400)
        assert any(v.rule == "file-too-long" for v in result.violations)
        # file-too-long is a warning, not an error
        size_viol = [v for v in result.violations if v.rule == "file-too-long"]
        assert all(v.level == ViolationLevel.WARNING for v in size_viol)

    def test_custom_max_lines(self, tmp_path):
        f = tmp_path / "SKILL.md"
        # Valid skill is ~20 lines; set limit to 5 to trigger
        f.write_text(VALID_SKILL, encoding="utf-8")
        result = validate_skill(f, max_lines=5)
        assert any(v.rule == "file-too-long" for v in result.violations)


# ---------------------------------------------------------------------------
# Unit: forbidden syntax
# ---------------------------------------------------------------------------


class TestForbiddenSyntax:

    def test_templater_syntax_detected(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(SKILL_WITH_TEMPLATER, encoding="utf-8")
        result = validate_skill(f)
        assert any(v.rule == "no-templater" for v in result.violations)
        assert not result.passed

    def test_raw_html_detected(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(SKILL_WITH_RAW_HTML, encoding="utf-8")
        result = validate_skill(f)
        assert any(v.rule == "no-raw-html" for v in result.violations)
        assert not result.passed

    def test_violation_reports_line_number(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(SKILL_WITH_TEMPLATER, encoding="utf-8")
        result = validate_skill(f)
        templater_violations = [v for v in result.violations if v.rule == "no-templater"]
        assert all(v.line is not None for v in templater_violations)
        assert all(v.line > 0 for v in templater_violations)

    def test_clean_skill_no_forbidden_syntax(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        result = validate_skill(f)
        forbidden = [v for v in result.violations if v.rule in ("no-templater", "no-raw-html")]
        assert forbidden == []


# ---------------------------------------------------------------------------
# Unit: directory scanning
# ---------------------------------------------------------------------------


class TestDirectoryScanning:

    def test_scans_directory_recursively(self, skills_dir):
        validator = SkillValidator()
        result = validator.validate_directory(skills_dir)
        assert result.files_scanned >= 1

    def test_ignores_non_skill_markdown(self, skills_dir):
        """README.md without frontmatter should not be validated."""
        validator = SkillValidator()
        result = validator.validate_directory(skills_dir)
        paths = [r.path for r in result.results]
        assert not any("README.md" in p for p in paths)

    def test_nonexistent_dir_returns_empty(self, tmp_path):
        validator = SkillValidator()
        result = validator.validate_directory(tmp_path / "nonexistent")
        assert result.files_scanned == 0
        assert result.results == []

    def test_valid_skill_passes(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        validator = SkillValidator()
        result = validator.validate_directory(tmp_path)
        assert result.files_scanned == 1
        assert result.passed

    def test_mixed_valid_invalid_counts(self, skills_dir):
        validator = SkillValidator()
        result = validator.validate_directory(skills_dir)
        # The "valid" one should pass, "no-version" should fail
        assert result.files_scanned >= 2
        passed = [r for r in result.results if r.passed]
        failed = [r for r in result.results if not r.passed]
        assert len(passed) >= 1
        assert len(failed) >= 1


# ---------------------------------------------------------------------------
# Unit: FileResult and ValidationResult properties
# ---------------------------------------------------------------------------


class TestResultProperties:

    def test_file_result_passed_when_no_violations(self):
        r = FileResult(path="test.md", violations=[], line_count=10)
        assert r.passed is True
        assert r.error_count == 0
        assert r.warning_count == 0

    def test_file_result_failed_when_error(self):
        v = Violation(level=ViolationLevel.ERROR, rule="frontmatter-missing", message="No fm")
        r = FileResult(path="test.md", violations=[v], line_count=5)
        assert r.passed is False
        assert r.error_count == 1
        assert r.warning_count == 0

    def test_file_result_passed_with_only_warnings(self):
        v = Violation(level=ViolationLevel.WARNING, rule="file-too-long", message="Too long")
        r = FileResult(path="test.md", violations=[v], line_count=500)
        assert r.passed is True  # Warnings don't fail
        assert r.warning_count == 1

    def test_validation_result_aggregation(self):
        err = Violation(level=ViolationLevel.ERROR, rule="frontmatter-missing", message="err")
        warn = Violation(level=ViolationLevel.WARNING, rule="file-too-long", message="warn")
        r1 = FileResult(path="a.md", violations=[err], line_count=5)
        r2 = FileResult(path="b.md", violations=[warn], line_count=500)
        vr = ValidationResult(files_scanned=2, results=[r1, r2])
        assert vr.total_errors == 1
        assert vr.total_warnings == 1
        assert not vr.passed
        assert len(vr.files_with_errors) == 1


# ---------------------------------------------------------------------------
# Unit: report formats
# ---------------------------------------------------------------------------


class TestReportFormats:

    def test_text_report_structure(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        validator = SkillValidator()
        result = validator.validate_directory(tmp_path)
        report = validator.report(result, fmt="text")
        assert "Files scanned:" in report
        assert "PASS" in report

    def test_text_report_shows_violations(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(SKILL_MISSING_CRITICAL_RULES, encoding="utf-8")
        validator = SkillValidator()
        result = validator.validate_directory(tmp_path)
        report = validator.report(result, fmt="text")
        assert "FAIL" in report
        assert "section-missing" in report

    def test_json_report_is_valid_json(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        validator = SkillValidator()
        result = validator.validate_directory(tmp_path)
        report = validator.report(result, fmt="json")
        data = json.loads(report)
        assert "files_scanned" in data
        assert "summary" in data
        assert "files" in data

    def test_json_report_summary_fields(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        validator = SkillValidator()
        result = validator.validate_directory(tmp_path)
        data = json.loads(validator.report(result, fmt="json"))
        summary = data["summary"]
        assert "passed" in summary
        assert "total_errors" in summary
        assert "total_warnings" in summary
        assert "files_with_errors" in summary

    def test_json_report_includes_violations(self, tmp_path):
        f = tmp_path / "SKILL.md"
        f.write_text(SKILL_MISSING_CRITICAL_RULES, encoding="utf-8")
        validator = SkillValidator()
        result = validator.validate_directory(tmp_path)
        data = json.loads(validator.report(result, fmt="json"))
        assert data["summary"]["total_errors"] >= 1
        file_entry = data["files"][0]
        assert len(file_entry["violations"]) >= 1
        assert file_entry["violations"][0]["level"] == "error"


# ---------------------------------------------------------------------------
# Integration: CLI validate-skills command
# ---------------------------------------------------------------------------


class TestValidateSkillsCLI:

    def test_valid_skill_exits_zero(self, tmp_path, runner):
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        result = runner.invoke(main, ["validate-skills", str(tmp_path)])
        assert result.exit_code == 0

    def test_invalid_skill_exits_one(self, tmp_path, runner):
        f = tmp_path / "SKILL.md"
        # Missing version — has name: so it's a candidate, but fails validation
        f.write_text(SKILL_MISSING_VERSION, encoding="utf-8")
        result = runner.invoke(main, ["validate-skills", str(tmp_path)])
        assert result.exit_code == 1

    def test_no_skill_files_exits_zero(self, tmp_path, runner):
        # Only a README with no frontmatter
        (tmp_path / "README.md").write_text("# Not a skill\n", encoding="utf-8")
        result = runner.invoke(main, ["validate-skills", str(tmp_path)])
        assert result.exit_code == 0

    def test_json_output_format(self, tmp_path, runner):
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        result = runner.invoke(main, ["validate-skills", str(tmp_path), "--fmt", "json", "-q"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "files_scanned" in data

    def test_strict_flag_triggers_warning(self, tmp_path, runner):
        skill_no_examples = """\
---
name: no-examples
description: Missing examples section.
version: "1.0"
---

## Critical Rules

1. Rule one.
"""
        f = tmp_path / "SKILL.md"
        f.write_text(skill_no_examples, encoding="utf-8")
        # Without --strict, should pass (no errors)
        result = runner.invoke(main, ["validate-skills", str(tmp_path)])
        assert result.exit_code == 0

    def test_fail_on_warning_exits_one_for_warnings(self, tmp_path, runner):
        f = tmp_path / "SKILL.md"
        f.write_text(make_long_skill(500), encoding="utf-8")  # triggers file-too-long warning
        result = runner.invoke(main, [
            "validate-skills", str(tmp_path),
            "--max-lines", "400",
            "--fail-on", "warning",
        ])
        assert result.exit_code == 1

    def test_fail_on_error_ignores_warnings(self, tmp_path, runner):
        f = tmp_path / "SKILL.md"
        f.write_text(make_long_skill(500), encoding="utf-8")  # triggers file-too-long warning only
        result = runner.invoke(main, [
            "validate-skills", str(tmp_path),
            "--max-lines", "400",
            "--fail-on", "error",
        ])
        assert result.exit_code == 0

    def test_max_lines_option(self, tmp_path, runner):
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        result = runner.invoke(main, [
            "validate-skills", str(tmp_path), "--max-lines", "5",
        ])
        # Warning only, default fail-on=error → should still pass
        assert result.exit_code == 0

    def test_single_file_target(self, tmp_path, runner):
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        result = runner.invoke(main, ["validate-skills", str(f)])
        assert result.exit_code == 0

    def test_single_invalid_file_target(self, tmp_path, runner):
        f = tmp_path / "SKILL.md"
        f.write_text(SKILL_MISSING_FRONTMATTER, encoding="utf-8")
        result = runner.invoke(main, ["validate-skills", str(f)])
        assert result.exit_code == 1

    def test_default_path_is_cwd(self, tmp_path, runner):
        """validate-skills with no PATH arg uses current dir."""
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        # Run from tmp_path
        with runner.isolated_filesystem(temp_dir=tmp_path):
            import shutil
            shutil.copy(str(f), "SKILL.md")
            result = runner.invoke(main, ["validate-skills"])
        assert result.exit_code == 0

    def test_templater_causes_failure(self, tmp_path, runner):
        f = tmp_path / "SKILL.md"
        f.write_text(SKILL_WITH_TEMPLATER, encoding="utf-8")
        result = runner.invoke(main, ["validate-skills", str(tmp_path)])
        assert result.exit_code == 1

    def test_quiet_flag_suppresses_stderr(self, tmp_path, runner):
        f = tmp_path / "SKILL.md"
        f.write_text(VALID_SKILL, encoding="utf-8")
        result = runner.invoke(main, ["validate-skills", str(tmp_path), "-q"])
        # With quiet, the progress line in stderr should not appear in output
        assert "Scanning" not in result.output
