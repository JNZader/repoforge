"""Decision Intelligence — extract WHY from code via inline comments
and git history. Captures architectural decisions, tradeoffs, and
rationale that static analysis misses.

Scans for patterns like:
  // WHY: ...
  // DECISION: ...
  // TRADEOFF: ...
  # WHY: ...
  /* DECISION: ... */
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Decision:
    """A captured architectural decision from source code."""
    marker: str        # WHY, DECISION, TRADEOFF, TODO, HACK, NOTE
    text: str          # The decision content
    file: str          # Relative file path
    line: int          # Line number (1-indexed)
    context: str = ""  # Surrounding code for context


# Regex patterns for decision markers in comments
_MARKERS = ["WHY", "DECISION", "TRADEOFF", "HACK", "NOTE", "FIXME", "REVIEW"]
_MARKER_PATTERN = re.compile(
    r"""
    (?:                     # Comment prefix
        //\s*               # C-style single-line
        | \#\s*             # Python/Shell
        | \*\s*             # Block comment line
        | /\*\s*            # Block comment start
    )
    (""" + "|".join(_MARKERS) + r""")  # Marker keyword
    :\s*                    # Colon + space
    (.+?)                   # Decision text (non-greedy)
    \s*$                    # End of line
    """,
    re.VERBOSE | re.IGNORECASE,
)


def extract_decisions_from_content(
    content: str, file_path: str, *, context_lines: int = 1,
) -> list[Decision]:
    """Extract decision markers from file content."""
    decisions: list[Decision] = []
    lines = content.split("\n")

    for i, line in enumerate(lines):
        match = _MARKER_PATTERN.search(line)
        if not match:
            continue

        marker = match.group(1).upper()
        text = match.group(2).strip()

        # Skip placeholder/example patterns (e.g., "..." in docstrings)
        cleaned = text.rstrip("*/").strip()
        if not cleaned or cleaned == "..." or len(cleaned) < 5:
            continue

        # Gather surrounding context
        start = max(0, i - context_lines)
        end = min(len(lines), i + context_lines + 1)
        ctx = "\n".join(lines[start:end])

        decisions.append(Decision(
            marker=marker,
            text=text,
            file=file_path,
            line=i + 1,
            context=ctx,
        ))

    return decisions


def extract_decisions_from_file(
    file_path: Path, base_dir: Path, *, context_lines: int = 1,
) -> list[Decision]:
    """Extract decisions from a single file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return []

    rel = str(file_path.relative_to(base_dir))
    return extract_decisions_from_content(content, rel, context_lines=context_lines)


# Skip directories
_SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "__pycache__", "target",
    "vendor", ".venv", "venv", ".tox", "coverage", ".next",
}

# Scan only text-like files
_TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
    ".rb", ".php", ".c", ".cpp", ".h", ".hpp", ".cs", ".swift",
    ".kt", ".lua", ".sh", ".bash", ".zsh", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".conf",
}


def scan_directory(
    directory: Path, *, context_lines: int = 1,
) -> list[Decision]:
    """Recursively scan a directory for decision markers."""
    decisions: list[Decision] = []

    for child in sorted(directory.iterdir()):
        if child.is_dir():
            if child.name in _SKIP_DIRS:
                continue
            decisions.extend(scan_directory(child, context_lines=context_lines))
        elif child.is_file() and child.suffix in _TEXT_EXTENSIONS:
            decisions.extend(
                extract_decisions_from_file(child, directory, context_lines=context_lines)
            )

    return decisions


@dataclass
class DecisionReport:
    """Summary of decisions found in a codebase."""
    decisions: list[Decision] = field(default_factory=list)

    @property
    def by_marker(self) -> dict[str, list[Decision]]:
        result: dict[str, list[Decision]] = {}
        for d in self.decisions:
            result.setdefault(d.marker, []).append(d)
        return result

    @property
    def by_file(self) -> dict[str, list[Decision]]:
        result: dict[str, list[Decision]] = {}
        for d in self.decisions:
            result.setdefault(d.file, []).append(d)
        return result

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for d in self.decisions:
            counts[d.marker] = counts.get(d.marker, 0) + 1
        return counts

    def to_markdown(self) -> str:
        if not self.decisions:
            return "No decisions found.\n"

        lines = ["# Decision Intelligence Report\n"]
        for marker, group in sorted(self.by_marker.items()):
            lines.append(f"## {marker} ({len(group)})\n")
            for d in group:
                lines.append(f"- **{d.file}:{d.line}** — {d.text}")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> list[dict[str, Any]]:
        return [
            {
                "marker": d.marker,
                "text": d.text,
                "file": d.file,
                "line": d.line,
                "context": d.context,
            }
            for d in self.decisions
        ]

    @classmethod
    def from_dict(cls, data: list[dict[str, Any]]) -> DecisionReport:
        report = cls()
        for item in data:
            report.decisions.append(Decision(
                marker=item["marker"],
                text=item["text"],
                file=item["file"],
                line=item["line"],
                context=item.get("context", ""),
            ))
        return report
