"""Style enforcement — rule-based checks for generated documentation.

Checks for common quality issues: empty sections, missing headings,
overly long paragraphs, etc. No LLM required.

Usage:
    from repoforge.style import check_style
    violations = check_style(markdown_content)
    for v in violations:
        print(f"{v.severity}: {v.rule} — {v.message}")
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class StyleRule:
    """A documentation style rule."""
    name: str
    description: str
    severity: str = "warning"  # "warning" | "error"


@dataclass
class StyleViolation:
    """A detected style violation."""
    rule: str
    message: str
    severity: str = "warning"
    line: int | None = None


DEFAULT_RULES = [
    StyleRule("missing_h1", "Document must start with an H1 heading"),
    StyleRule("empty_section", "Section heading with no content below it"),
    StyleRule("long_paragraph", "Paragraph exceeds 150 words"),
    StyleRule("no_formatting", "No tables, lists, or code blocks found", severity="warning"),
    StyleRule("consecutive_headings", "Two headings with no content between them"),
]


def check_style(content: str) -> list[StyleViolation]:
    """Check markdown content against style rules. Returns violations."""
    if not content or not content.strip():
        return []

    violations: list[StyleViolation] = []

    _check_missing_h1(content, violations)
    _check_empty_sections(content, violations)
    _check_long_paragraphs(content, violations)
    _check_no_formatting(content, violations)

    return violations


def _check_missing_h1(content: str, violations: list) -> None:
    lines = content.strip().split("\n")
    has_h1 = any(line.startswith("# ") and not line.startswith("## ") for line in lines)
    if not has_h1:
        violations.append(StyleViolation(
            rule="missing_h1",
            message="Document has no H1 heading",
            severity="error",
        ))


def _check_empty_sections(content: str, violations: list) -> None:
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            continue
        # Look ahead for content before next heading
        has_content = False
        for j in range(i + 1, min(i + 20, len(lines))):
            next_line = lines[j].strip()
            if next_line.startswith("#"):
                break
            if next_line and not next_line.startswith("<!--"):
                has_content = True
                break
        if not has_content and i < len(lines) - 1:
            violations.append(StyleViolation(
                rule="empty_section",
                message=f"Empty section: {line.strip()}",
                severity="warning",
                line=i + 1,
            ))


def _check_long_paragraphs(content: str, violations: list) -> None:
    paragraphs = content.split("\n\n")
    for para in paragraphs:
        para = para.strip()
        if not para or para.startswith("#") or para.startswith("|") or para.startswith("```"):
            continue
        words = len(para.split())
        if words > 150:
            violations.append(StyleViolation(
                rule="long_paragraph",
                message=f"Paragraph has {words} words (max recommended: 150)",
                severity="warning",
            ))


def _check_no_formatting(content: str, violations: list) -> None:
    has_table = "|" in content and "---" in content
    has_list = bool(re.search(r"^[\s]*[-*]\s", content, re.MULTILINE))
    has_code = "```" in content

    if not has_table and not has_list and not has_code:
        if len(content.split()) > 50:  # Only flag if substantial content
            violations.append(StyleViolation(
                rule="no_formatting",
                message="No tables, lists, or code blocks found",
                severity="warning",
            ))
