"""Decision Intelligence v2 — decision registry with git history and staleness.

Extends decision_intel.py with:
  1. Git history mining: extract decisions from commit messages and PR descriptions
  2. Decision registry: link decisions to code nodes (files/functions)
  3. Staleness tracking: flag decisions where the linked code has changed
     significantly since the decision was recorded

Sources:
  - Inline markers: WHY:, DECISION:, TRADEOFF: (from v1)
  - Commit messages: lines matching decision patterns
  - Inline markers with git blame: detect when the decision was written
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .decision_intel import (
    _MARKERS,
    _TEXT_EXTENSIONS,
    Decision,
    DecisionReport,
    extract_decisions_from_content,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DecisionEntry:
    """A decision in the registry, enriched with git metadata."""

    marker: str
    """Decision type: WHY, DECISION, TRADEOFF, etc."""

    text: str
    """The decision text."""

    file: str
    """Relative file path."""

    line: int
    """Line number (1-indexed). 0 for commit-sourced decisions."""

    source: str
    """Where this decision came from: 'inline', 'commit', 'pr'."""

    author: str = ""
    """Git author who wrote this decision."""

    date: str = ""
    """ISO date when the decision was written."""

    commit_sha: str = ""
    """Commit SHA where this decision was introduced or found."""

    lines_changed_since: int = 0
    """Number of lines changed in the file since the decision was written."""

    is_stale: bool = False
    """True if the decision may be outdated (file changed significantly)."""

    staleness_reason: str = ""
    """Explanation of why this decision is considered stale."""

    @property
    def confidence(self) -> str:
        """How confident we are that this decision is still valid."""
        if self.is_stale:
            return "stale"
        if self.lines_changed_since > 50:
            return "low"
        if self.lines_changed_since > 10:
            return "medium"
        return "high"


@dataclass
class DecisionRegistry:
    """Full decision registry with staleness tracking."""

    entries: list[DecisionEntry] = field(default_factory=list)
    """All decisions found."""

    commits_analyzed: int = 0
    """Number of commits scanned for decisions."""

    files_scanned: int = 0
    """Number of source files scanned for inline markers."""

    @property
    def stale_decisions(self) -> list[DecisionEntry]:
        """Decisions flagged as potentially stale."""
        return [e for e in self.entries if e.is_stale]

    @property
    def by_file(self) -> dict[str, list[DecisionEntry]]:
        """Group decisions by file."""
        result: dict[str, list[DecisionEntry]] = {}
        for e in self.entries:
            result.setdefault(e.file, []).append(e)
        return result

    @property
    def by_marker(self) -> dict[str, list[DecisionEntry]]:
        """Group decisions by marker type."""
        result: dict[str, list[DecisionEntry]] = {}
        for e in self.entries:
            result.setdefault(e.marker, []).append(e)
        return result

    @property
    def by_source(self) -> dict[str, list[DecisionEntry]]:
        """Group decisions by source."""
        result: dict[str, list[DecisionEntry]] = {}
        for e in self.entries:
            result.setdefault(e.source, []).append(e)
        return result


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


_COMMIT_DECISION_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:"
    + "|".join(_MARKERS)
    + r"):\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)


def _extract_decisions_from_commits(
    repo_path: str,
    max_commits: int = 500,
    since: str | None = None,
) -> list[DecisionEntry]:
    """Extract decisions from git commit messages."""
    repo = str(Path(repo_path).resolve())
    cmd = [
        "git", "-C", repo, "log",
        "--pretty=format:%H%n%an%n%aI%n%s%n%b%n---END---",
        f"--max-count={max_commits}",
    ]
    if since:
        cmd.append(f"--since={since}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            logger.warning("git log failed: %s", result.stderr.strip())
            return []
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("git log failed")
        return []

    entries: list[DecisionEntry] = []
    commits_raw = result.stdout.split("---END---")

    for block in commits_raw:
        block = block.strip()
        if not block:
            continue
        parts = block.split("\n", 3)
        if len(parts) < 3:
            continue

        sha = parts[0].strip()
        author = parts[1].strip()
        date = parts[2].strip()
        message = "\n".join(parts[3:]) if len(parts) > 3 else ""

        # Search for decision patterns in commit message
        full_text = message
        for match in _COMMIT_DECISION_PATTERN.finditer(full_text):
            marker_match = re.search(
                r"(" + "|".join(_MARKERS) + r"):",
                match.group(0),
                re.IGNORECASE,
            )
            if not marker_match:
                continue
            marker = marker_match.group(1).upper()
            text = match.group(1).strip()
            if len(text) < 5:
                continue

            # Get changed files for this commit
            files = _get_commit_files(repo, sha)
            file_ref = files[0] if files else "<commit>"

            entries.append(DecisionEntry(
                marker=marker,
                text=text,
                file=file_ref,
                line=0,
                source="commit",
                author=author,
                date=date,
                commit_sha=sha[:8],
            ))

    return entries


def _get_commit_files(repo: str, sha: str) -> list[str]:
    """Get files changed in a specific commit."""
    try:
        result = subprocess.run(
            ["git", "-C", repo, "diff-tree", "--no-commit-id", "--name-only", "-r", sha],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return [f for f in result.stdout.strip().splitlines() if f]
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return []


def _blame_line(repo: str, file_path: str, line: int) -> tuple[str, str, str]:
    """Get git blame info for a specific line.

    Returns: (commit_sha, author, date)
    """
    try:
        result = subprocess.run(
            [
                "git", "-C", repo, "blame", "-L", f"{line},{line}",
                "--porcelain", file_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return ("", "", "")

        sha = ""
        author = ""
        date = ""
        for out_line in result.stdout.splitlines():
            if not sha and len(out_line) >= 40 and out_line[0] != "\t":
                sha = out_line.split()[0][:8]
            elif out_line.startswith("author "):
                author = out_line[7:]
            elif out_line.startswith("author-time "):
                # Unix timestamp — convert to ISO date
                try:
                    import datetime

                    ts = int(out_line[12:].strip())
                    date = datetime.datetime.fromtimestamp(
                        ts, tz=datetime.timezone.utc,
                    ).strftime("%Y-%m-%d")
                except (ValueError, OSError):
                    pass
        return (sha, author, date)
    except (subprocess.SubprocessError, FileNotFoundError):
        return ("", "", "")


def _count_changes_since(repo: str, file_path: str, since_sha: str) -> int:
    """Count lines changed in a file since a given commit."""
    if not since_sha:
        return 0
    try:
        result = subprocess.run(
            ["git", "-C", repo, "diff", "--stat", f"{since_sha}..HEAD", "--", file_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return 0

        # Parse "N insertions(+), M deletions(-)" from last line
        for out_line in reversed(result.stdout.strip().splitlines()):
            nums = re.findall(r"(\d+) (?:insertion|deletion)", out_line)
            if nums:
                return sum(int(n) for n in nums)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return 0


# ---------------------------------------------------------------------------
# File scanning with git enrichment
# ---------------------------------------------------------------------------

# Directories to skip during scanning
_SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "__pycache__", "target",
    "vendor", ".venv", "venv", ".tox", "coverage", ".next",
}


def _scan_files_with_blame(
    repo_path: str,
    *,
    stale_threshold: int = 50,
) -> tuple[list[DecisionEntry], int]:
    """Scan source files for inline decision markers, enriched with git blame.

    Returns: (entries, files_scanned)
    """
    root = Path(repo_path).resolve()
    repo = str(root)
    entries: list[DecisionEntry] = []
    files_scanned = 0

    for path in _walk_source_files(root):
        files_scanned += 1
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        rel_path = str(path.relative_to(root))
        decisions = extract_decisions_from_content(content, rel_path)

        for d in decisions:
            sha, author, date = _blame_line(repo, rel_path, d.line)
            changes = _count_changes_since(repo, rel_path, sha)

            is_stale = changes > stale_threshold
            staleness_reason = ""
            if is_stale:
                staleness_reason = (
                    f"{changes} lines changed in {rel_path} since "
                    f"decision was written ({sha})"
                )

            entries.append(DecisionEntry(
                marker=d.marker,
                text=d.text,
                file=d.file,
                line=d.line,
                source="inline",
                author=author,
                date=date,
                commit_sha=sha,
                lines_changed_since=changes,
                is_stale=is_stale,
                staleness_reason=staleness_reason,
            ))

    return entries, files_scanned


def _walk_source_files(root: Path) -> list[Path]:
    """Walk source files, skipping vendor/build directories."""
    files: list[Path] = []

    def _walk(directory: Path) -> None:
        try:
            children = sorted(directory.iterdir())
        except OSError:
            return
        for child in children:
            if child.is_dir():
                if child.name in _SKIP_DIRS:
                    continue
                _walk(child)
            elif child.is_file() and child.suffix in _TEXT_EXTENSIONS:
                files.append(child)

    _walk(root)
    return files


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_decision_registry(
    repo_path: str,
    *,
    include_commits: bool = True,
    max_commits: int = 500,
    since: str | None = None,
    stale_threshold: int = 50,
    stale_only: bool = False,
) -> DecisionRegistry:
    """Build a complete decision registry from inline markers and git history.

    Args:
        repo_path: Path to the repository root.
        include_commits: Mine commit messages for decisions.
        max_commits: Max commits to analyze for commit-sourced decisions.
        since: Git date filter (e.g., '6 months ago').
        stale_threshold: Lines changed threshold to flag staleness.
        stale_only: Only return stale decisions.

    Returns:
        DecisionRegistry with all found decisions.
    """
    entries: list[DecisionEntry] = []
    commits_analyzed = 0

    # 1. Scan source files for inline markers (with blame)
    inline_entries, files_scanned = _scan_files_with_blame(
        repo_path, stale_threshold=stale_threshold,
    )
    entries.extend(inline_entries)

    # 2. Mine commit messages
    if include_commits:
        commit_entries = _extract_decisions_from_commits(
            repo_path, max_commits=max_commits, since=since,
        )
        entries.extend(commit_entries)
        commits_analyzed = max_commits  # Approximate

    # Filter stale-only if requested
    if stale_only:
        entries = [e for e in entries if e.is_stale]

    # Sort: stale first, then by file and line
    entries.sort(key=lambda e: (not e.is_stale, e.file, e.line))

    return DecisionRegistry(
        entries=entries,
        commits_analyzed=commits_analyzed,
        files_scanned=files_scanned,
    )


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


def format_decision_registry(registry: DecisionRegistry, *, stale_only: bool = False) -> str:
    """Format a decision registry as human-readable text."""
    entries = registry.stale_decisions if stale_only else registry.entries
    lines: list[str] = []

    lines.append("## Decision Registry")
    lines.append(f"**Total decisions**: {len(registry.entries)}")
    lines.append(f"**Stale decisions**: {len(registry.stale_decisions)}")
    lines.append(f"**Files scanned**: {registry.files_scanned}")
    if registry.commits_analyzed:
        lines.append(f"**Commits analyzed**: {registry.commits_analyzed}")
    lines.append("")

    if not entries:
        lines.append("No decisions found.")
        return "\n".join(lines)

    # Summary by marker
    by_marker = registry.by_marker
    lines.append("### Summary by type")
    for marker in sorted(by_marker.keys()):
        count = len(by_marker[marker])
        stale = sum(1 for e in by_marker[marker] if e.is_stale)
        stale_str = f" ({stale} stale)" if stale else ""
        lines.append(f"- **{marker}**: {count}{stale_str}")
    lines.append("")

    # Stale decisions (always shown first)
    stale = registry.stale_decisions
    if stale:
        lines.append(f"### Stale Decisions ({len(stale)})")
        lines.append("These decisions may be outdated — the associated code has changed significantly.")
        lines.append("")
        for e in stale:
            lines.append(f"- **{e.marker}** `{e.file}:{e.line}` — {e.text}")
            lines.append(f"  - Source: {e.source} | Author: {e.author or '?'} | Date: {e.date or '?'}")
            lines.append(f"  - Staleness: {e.staleness_reason}")
        lines.append("")

    if not stale_only:
        # Active decisions by file
        active = [e for e in entries if not e.is_stale]
        if active:
            lines.append(f"### Active Decisions ({len(active)})")
            current_file = ""
            for e in active:
                if e.file != current_file:
                    current_file = e.file
                    lines.append(f"\n#### `{current_file}`")
                loc = f":{e.line}" if e.line else ""
                lines.append(f"- **{e.marker}**{loc} — {e.text}")
                meta_parts = []
                if e.author:
                    meta_parts.append(f"Author: {e.author}")
                if e.date:
                    meta_parts.append(f"Date: {e.date}")
                if e.source != "inline":
                    meta_parts.append(f"Source: {e.source}")
                if e.confidence != "high":
                    meta_parts.append(f"Confidence: {e.confidence}")
                if meta_parts:
                    lines.append(f"  - {' | '.join(meta_parts)}")
            lines.append("")

    return "\n".join(lines)
