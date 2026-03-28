"""UX utilities — progress tracking, diff viewer, summary formatting.

No external dependencies (no rich/textual). Uses plain text formatting
that works in any terminal.

Usage:
    from repoforge.ux import ProgressTracker, diff_docs, format_summary
    tracker = ProgressTracker(total=7, label="Generating")
    tracker.advance("01-overview.md", status="ok")
    print(tracker.format_bar())
"""

from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Progress tracker
# ---------------------------------------------------------------------------


class ProgressTracker:
    """Track progress of multi-step operations."""

    def __init__(self, total: int, label: str = "Progress") -> None:
        self.total = total
        self.label = label
        self.completed = 0
        self.history: list[dict] = []

    def advance(self, item: str, status: str = "ok") -> None:
        self.completed += 1
        self.history.append({"item": item, "status": status})

    @property
    def percentage(self) -> float:
        if self.total <= 0:
            return 100.0
        return round((self.completed / self.total) * 100, 1)

    @property
    def is_done(self) -> bool:
        return self.total <= 0 or self.completed >= self.total

    def format_bar(self, width: int = 30) -> str:
        if self.total <= 0:
            return f"{self.label}: done"
        filled = int(width * self.completed / self.total)
        bar = "█" * filled + "░" * (width - filled)
        return f"{self.label} [{bar}] {self.completed}/{self.total} ({self.percentage}%)"


# ---------------------------------------------------------------------------
# Diff viewer
# ---------------------------------------------------------------------------


@dataclass
class DiffResult:
    """Result of comparing two document versions."""

    has_changes: bool = False
    additions: int = 0
    deletions: int = 0
    modifications: int = 0
    diff_lines: list[str] = field(default_factory=list)

    def format_unified(self) -> str:
        return "\n".join(self.diff_lines)

    def summary(self) -> str:
        if not self.has_changes:
            return "No changes"
        parts = []
        if self.additions:
            parts.append(f"+{self.additions} added")
        if self.deletions:
            parts.append(f"-{self.deletions} removed")
        if self.modifications:
            parts.append(f"~{self.modifications} modified")
        return ", ".join(parts)


def diff_docs(old: str, new: str) -> DiffResult:
    """Compare two document versions line by line."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)

    diff = list(difflib.unified_diff(old_lines, new_lines, fromfile="old", tofile="new"))

    if not diff:
        return DiffResult()

    additions = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    deletions = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))

    return DiffResult(
        has_changes=True,
        additions=additions,
        deletions=deletions,
        modifications=min(additions, deletions),
        diff_lines=[l.rstrip("\n") for l in diff],
    )


# ---------------------------------------------------------------------------
# Summary formatter
# ---------------------------------------------------------------------------


def format_summary(
    project_name: str,
    chapters_generated: int,
    total_tokens: int,
    cost: float,
    duration_seconds: float,
    errors: int = 0,
) -> str:
    """Format a human-readable generation summary."""
    # Duration
    if duration_seconds >= 60:
        mins = int(duration_seconds // 60)
        secs = int(duration_seconds % 60)
        duration_str = f"{mins}m {secs}s"
    else:
        duration_str = f"{duration_seconds:.1f}s"

    # Tokens
    if total_tokens >= 1_000_000:
        token_str = f"{total_tokens / 1_000_000:.1f}M"
    elif total_tokens >= 1_000:
        token_str = f"{total_tokens / 1_000:.0f}K"
    else:
        token_str = str(total_tokens)

    lines = [
        f"📊 {project_name} — Generation Summary",
        f"   Chapters: {chapters_generated}",
        f"   Tokens:   {token_str}",
        f"   Cost:     ${cost:.4f}",
        f"   Duration: {duration_str}",
    ]

    if errors:
        lines.append(f"   ⚠️  Errors:  {errors} error(s)")

    return "\n".join(lines)
