"""
skill_validator.py - Deterministic validator for SKILL.md files.

Checks SKILL.md files against a standard format without requiring an LLM.
Suitable for CI pipelines and pre-push hooks.

Checks performed:
  1. YAML frontmatter exists (--- block at top) with required keys: name, description, version
  2. Required sections present: ## Critical Rules (at minimum)
  3. File size within limits (default: 400 lines)
  4. No forbidden syntax (Templater <% blocks, raw HTML, etc.)
  5. Optional: ## Examples section presence (--strict mode)

Usage:
    from repoforge.skill_validator import validate_skill, SkillValidator

    result = validate_skill("/path/to/SKILL.md")
    if result.violations:
        for v in result.violations:
            print(v)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class ViolationLevel(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class Violation:
    """A single validation violation found in a SKILL.md file."""

    level: ViolationLevel
    rule: str
    message: str
    line: int | None = None  # 1-based line number, or None for file-level

    def __str__(self) -> str:
        loc = f":{self.line}" if self.line is not None else ""
        return f"[{self.level.value.upper()}] {self.rule}{loc}: {self.message}"


@dataclass
class FileResult:
    """Validation result for a single SKILL.md file."""

    path: str
    violations: list[Violation] = field(default_factory=list)
    line_count: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.level == ViolationLevel.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.level == ViolationLevel.WARNING)

    @property
    def passed(self) -> bool:
        return self.error_count == 0


@dataclass
class ValidationResult:
    """Aggregated results from validating one or more SKILL.md files."""

    files_scanned: int = 0
    results: list[FileResult] = field(default_factory=list)

    @property
    def total_errors(self) -> int:
        return sum(r.error_count for r in self.results)

    @property
    def total_warnings(self) -> int:
        return sum(r.warning_count for r in self.results)

    @property
    def files_with_errors(self) -> list[FileResult]:
        return [r for r in self.results if not r.passed]

    @property
    def passed(self) -> bool:
        return self.total_errors == 0


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Frontmatter: must start at line 1
_FRONTMATTER_START_RE = re.compile(r"^---\s*$")
_FRONTMATTER_END_RE = re.compile(r"^---\s*$")

# Required frontmatter keys
_REQUIRED_FM_KEYS = ("name", "description", "version")

# Required sections (minimum set)
_REQUIRED_SECTIONS = ("## Critical Rules",)

# Optional strict sections
_STRICT_SECTIONS = ("## Examples",)

# Forbidden syntax patterns: (rule_id, pattern, description)
_FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "no-templater",
        re.compile(r"<%[-_]?"),
        "Templater syntax (<%...) is forbidden in SKILL.md files",
    ),
    (
        "no-raw-html",
        re.compile(r"<(?!--)[a-zA-Z][^>]*>"),
        "Raw HTML tags are forbidden — use Markdown formatting instead",
    ),
]


# ---------------------------------------------------------------------------
# SkillValidator
# ---------------------------------------------------------------------------


class SkillValidator:
    """Validates SKILL.md files against the standard format."""

    def __init__(
        self,
        max_lines: int = 400,
        strict: bool = False,
        fail_on: str = "error",
    ) -> None:
        """
        Args:
            max_lines: Maximum allowed lines per file.
            strict: If True, also require ## Examples section.
            fail_on: Severity level that triggers non-zero exit — 'error' or 'warning'.
        """
        self.max_lines = max_lines
        self.strict = strict
        self.fail_on = fail_on

    # -- Frontmatter parsing --------------------------------------------------

    def _parse_frontmatter(self, lines: list[str]) -> tuple[dict[str, str], int]:
        """Extract YAML frontmatter from file lines.

        Returns:
            (key_value_dict, end_line_index) — end_line_index is the line after ---.
            Returns ({}, 0) if no valid frontmatter found.
        """
        if not lines or not _FRONTMATTER_START_RE.match(lines[0]):
            return {}, 0

        fm_lines = []
        end_idx = 0
        for i, line in enumerate(lines[1:], start=1):
            if _FRONTMATTER_END_RE.match(line):
                end_idx = i + 1  # line after closing ---
                break
            fm_lines.append(line)
        else:
            # No closing --- found
            return {}, 0

        # Simple key: value extraction (handles multi-line block scalars correctly)
        fm: dict[str, str] = {}
        i = 0
        while i < len(fm_lines):
            line = fm_lines[i]
            m = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                # Block scalar indicators (>, |): value is on continuation lines
                if val in (">", "|", ">-", "|-", ">+", "|+"):
                    # Collect indented continuation lines
                    parts: list[str] = []
                    i += 1
                    while i < len(fm_lines) and (fm_lines[i].startswith(" ") or fm_lines[i].startswith("\t")):
                        parts.append(fm_lines[i].strip())
                        i += 1
                    fm[key] = " ".join(parts)
                    continue  # already advanced i
                else:
                    val = val.strip().strip("\"'")
                    fm[key] = val
            i += 1

        return fm, end_idx

    # -- File-level checks ----------------------------------------------------

    def _check_frontmatter(self, lines: list[str], violations: list[Violation]) -> dict[str, str]:
        """Check frontmatter exists and has required keys."""
        if not lines or not _FRONTMATTER_START_RE.match(lines[0]):
            violations.append(Violation(
                level=ViolationLevel.ERROR,
                rule="frontmatter-missing",
                message="No YAML frontmatter found. File must start with --- block.",
                line=1,
            ))
            return {}

        fm, end_idx = self._parse_frontmatter(lines)

        if end_idx == 0:
            violations.append(Violation(
                level=ViolationLevel.ERROR,
                rule="frontmatter-unclosed",
                message="Frontmatter block opened with --- but never closed.",
                line=1,
            ))
            return {}

        # Check required keys
        for key in _REQUIRED_FM_KEYS:
            if key not in fm or not fm[key]:
                violations.append(Violation(
                    level=ViolationLevel.ERROR,
                    rule=f"frontmatter-missing-{key}",
                    message=f"Frontmatter missing required key: '{key}'",
                ))

        return fm

    def _check_sections(self, content: str, violations: list[Violation]) -> None:
        """Check required section headers are present."""
        for section in _REQUIRED_SECTIONS:
            if section not in content:
                violations.append(Violation(
                    level=ViolationLevel.ERROR,
                    rule="section-missing",
                    message=f"Required section not found: '{section}'",
                ))

        if self.strict:
            for section in _STRICT_SECTIONS:
                if section not in content:
                    violations.append(Violation(
                        level=ViolationLevel.WARNING,
                        rule="section-missing-strict",
                        message=f"Strict mode: required section not found: '{section}'",
                    ))

    def _check_line_count(self, line_count: int, violations: list[Violation]) -> None:
        """Check file is within line limit."""
        if line_count > self.max_lines:
            violations.append(Violation(
                level=ViolationLevel.WARNING,
                rule="file-too-long",
                message=(
                    f"File has {line_count} lines, exceeds limit of {self.max_lines}. "
                    "Consider splitting into sub-skills."
                ),
            ))

    def _check_forbidden_syntax(self, lines: list[str], violations: list[Violation]) -> None:
        """Check for forbidden syntax patterns."""
        for line_no, line in enumerate(lines, start=1):
            for rule_id, pattern, description in _FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    violations.append(Violation(
                        level=ViolationLevel.ERROR,
                        rule=rule_id,
                        message=description,
                        line=line_no,
                    ))

    # -- Public API -----------------------------------------------------------

    def validate_file(self, path: str | Path) -> FileResult:
        """Validate a single SKILL.md file.

        Args:
            path: Path to the SKILL.md file.

        Returns:
            FileResult with all violations found.
        """
        path = Path(path)
        violations: list[Violation] = []

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return FileResult(
                path=str(path),
                violations=[Violation(
                    level=ViolationLevel.ERROR,
                    rule="file-unreadable",
                    message=f"Cannot read file: {e}",
                )],
            )

        lines = content.splitlines()
        line_count = len(lines)

        # Run checks
        self._check_frontmatter(lines, violations)
        self._check_sections(content, violations)
        self._check_line_count(line_count, violations)
        self._check_forbidden_syntax(lines, violations)

        return FileResult(
            path=str(path),
            violations=violations,
            line_count=line_count,
        )

    def validate_directory(
        self,
        path: str | Path,
        glob_pattern: str = "**/*.md",
    ) -> ValidationResult:
        """Validate all SKILL.md files in a directory recursively.

        A file is treated as a SKILL.md candidate if:
          - It matches the glob pattern
          - Its content starts with a frontmatter block containing a 'name:' field

        Args:
            path: Root directory to search.
            glob_pattern: Glob pattern for candidate files.

        Returns:
            ValidationResult with per-file results.
        """
        root = Path(path)
        if not root.exists():
            return ValidationResult()

        results: list[FileResult] = []
        candidates = sorted(root.glob(glob_pattern))

        for md_file in candidates:
            if not md_file.is_file():
                continue

            # Peek: only validate files that look like skills (have frontmatter + name:)
            try:
                peek = md_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            if not _is_skill_candidate(peek):
                continue

            result = self.validate_file(md_file)
            results.append(result)

        return ValidationResult(
            files_scanned=len(results),
            results=results,
        )

    # -- Reporting ------------------------------------------------------------

    def report(self, result: ValidationResult, fmt: str = "text") -> str:
        """Format a ValidationResult into a human-readable report.

        Args:
            result: The validation result to format.
            fmt: Output format — 'text' or 'json'.

        Returns:
            Formatted report string.
        """
        if fmt == "json":
            return _report_json(result)
        return _report_text(result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_skill_candidate(content: str) -> bool:
    """Return True if the file looks like a SKILL.md (has frontmatter with name:)."""
    lines = content.splitlines()
    if not lines:
        return False

    # Must start with ---
    if not _FRONTMATTER_START_RE.match(lines[0]):
        return False

    # Must have name: key somewhere in the frontmatter
    for line in lines[1:]:
        if _FRONTMATTER_END_RE.match(line):
            break
        if re.match(r"^name\s*:", line):
            return True

    return False


# ---------------------------------------------------------------------------
# Report formatters
# ---------------------------------------------------------------------------


def _report_text(result: ValidationResult) -> str:
    """Format as plain text."""
    lines: list[str] = []

    lines.append(f"Files scanned: {result.files_scanned}")
    lines.append(
        f"Results: {len(result.files_with_errors)} file(s) with errors, "
        f"{result.total_errors} error(s), "
        f"{result.total_warnings} warning(s)"
    )
    lines.append("")

    if not result.results:
        lines.append("No SKILL.md files found matching criteria.")
        return "\n".join(lines)

    for file_result in result.results:
        status = "PASS" if file_result.passed else "FAIL"
        lines.append(f"  [{status}] {file_result.path} ({file_result.line_count} lines)")
        for v in file_result.violations:
            loc = f":{v.line}" if v.line is not None else ""
            lines.append(f"         [{v.level.value.upper()}] {v.rule}{loc}: {v.message}")

    lines.append("")

    if result.passed:
        lines.append("All SKILL.md files passed validation.")
    else:
        lines.append(
            f"Validation FAILED: {result.total_errors} error(s) across "
            f"{len(result.files_with_errors)} file(s)."
        )

    return "\n".join(lines)


def _report_json(result: ValidationResult) -> str:
    """Format as JSON."""
    data = {
        "files_scanned": result.files_scanned,
        "summary": {
            "passed": result.passed,
            "total_errors": result.total_errors,
            "total_warnings": result.total_warnings,
            "files_with_errors": len(result.files_with_errors),
        },
        "files": [
            {
                "path": r.path,
                "line_count": r.line_count,
                "passed": r.passed,
                "errors": r.error_count,
                "warnings": r.warning_count,
                "violations": [
                    {
                        "level": v.level.value,
                        "rule": v.rule,
                        "message": v.message,
                        "line": v.line,
                    }
                    for v in r.violations
                ],
            }
            for r in result.results
        ],
    }
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def validate_skill(
    path: str | Path,
    max_lines: int = 400,
    strict: bool = False,
) -> FileResult:
    """Validate a single SKILL.md file.

    Convenience wrapper for CLI and programmatic use.

    Args:
        path: Path to the SKILL.md file.
        max_lines: Maximum allowed lines.
        strict: If True, also require ## Examples section.

    Returns:
        FileResult with all violations found.
    """
    validator = SkillValidator(max_lines=max_lines, strict=strict)
    return validator.validate_file(path)
