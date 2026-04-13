"""Co-change pair detection — find files that always change together.

Mines git history to find files that frequently co-occur in the same commit
without having an import relationship (hidden coupling). These are candidates
for:
- Extract shared module
- Document implicit dependency
- Merge into same module

Algorithm:
  1. Walk git log, collect file sets per commit
  2. For each pair of files that co-occur, count frequency
  3. Compute Jaccard similarity: |A ∩ B| / |A ∪ B|
  4. Filter by threshold (default 0.5)
  5. Optionally cross-reference with dependency graph to flag pairs
     that have NO import link (truly hidden coupling)
"""

from __future__ import annotations

import logging
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoChangePair:
    """A pair of files that frequently change together."""

    file_a: str
    file_b: str
    co_change_count: int
    """Number of commits where both files changed."""

    total_a: int
    """Total commits where file_a changed."""

    total_b: int
    """Total commits where file_b changed."""

    jaccard: float
    """Jaccard similarity: co_changes / (total_a + total_b - co_changes)."""

    has_import_link: bool | None = None
    """True if files have a direct import relationship. None if not checked."""

    @property
    def confidence(self) -> str:
        if self.jaccard >= 0.8:
            return "high"
        if self.jaccard >= 0.5:
            return "medium"
        return "low"


@dataclass
class CoChangeReport:
    """Full co-change analysis result."""

    pairs: list[CoChangePair] = field(default_factory=list)
    commits_analyzed: int = 0
    files_analyzed: int = 0
    threshold: float = 0.5

    @property
    def hidden_coupling(self) -> list[CoChangePair]:
        """Pairs with no import link — truly hidden coupling."""
        return [p for p in self.pairs if p.has_import_link is False]


# ---------------------------------------------------------------------------
# Git history mining
# ---------------------------------------------------------------------------


def _get_commit_file_sets(
    repo_path: str,
    max_commits: int = 500,
    since: str | None = None,
) -> list[set[str]]:
    """Extract file sets from git log.

    Returns a list of sets, each set containing the files changed in one commit.
    """
    repo = str(Path(repo_path).resolve())
    cmd = ["git", "-C", repo, "log", "--name-only", "--pretty=format:---COMMIT---",
           f"--max-count={max_commits}"]
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

    commits: list[set[str]] = []
    current: set[str] = set()

    for line in result.stdout.splitlines():
        line = line.strip()
        if line == "---COMMIT---":
            if current:
                commits.append(current)
            current = set()
        elif line:
            # Skip non-code files
            if not _is_code_file(line):
                continue
            current.add(line)

    if current:
        commits.append(current)

    return commits


def _is_code_file(path: str) -> bool:
    """Check if a file is a code file (not config/docs/assets)."""
    skip_extensions = {
        ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".lock",
        ".png", ".jpg", ".gif", ".svg", ".ico",
        ".css", ".scss", ".less",
        ".html", ".xml",
    }
    skip_names = {
        "package-lock.json", "yarn.lock", "uv.lock", "Cargo.lock",
        ".gitignore", ".editorconfig", "LICENSE", "README.md",
    }
    name = Path(path).name
    suffix = Path(path).suffix.lower()
    return name not in skip_names and suffix not in skip_extensions


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------


def detect_co_changes(
    repo_path: str,
    *,
    threshold: float = 0.5,
    min_commits: int = 3,
    max_commits: int = 500,
    since: str | None = None,
    check_imports: bool = True,
    max_files_per_commit: int = 20,
) -> CoChangeReport:
    """Detect co-change pairs from git history.

    Args:
        repo_path: Path to the repository root.
        threshold: Minimum Jaccard similarity to include (0.0-1.0).
        min_commits: Minimum co-change count to consider.
        max_commits: Maximum commits to analyze.
        since: Git date filter (e.g., "6 months ago").
        check_imports: Cross-reference with dependency graph.
        max_files_per_commit: Skip commits touching more files (likely merges).

    Returns:
        CoChangeReport with detected co-change pairs.
    """
    commit_sets = _get_commit_file_sets(repo_path, max_commits=max_commits, since=since)

    # Filter out large commits (merges, reformats)
    commit_sets = [s for s in commit_sets if len(s) <= max_files_per_commit]

    # Count per-file occurrences and co-occurrences
    file_counts: dict[str, int] = defaultdict(int)
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)

    for file_set in commit_sets:
        files = sorted(file_set)  # Sort for deterministic pair ordering
        for f in files:
            file_counts[f] += 1
        for a, b in combinations(files, 2):
            pair_counts[(a, b)] += 1

    # Compute Jaccard and filter
    pairs: list[CoChangePair] = []
    for (a, b), count in pair_counts.items():
        if count < min_commits:
            continue
        total_a = file_counts[a]
        total_b = file_counts[b]
        union = total_a + total_b - count
        jaccard = count / union if union > 0 else 0.0
        if jaccard < threshold:
            continue

        pairs.append(CoChangePair(
            file_a=a,
            file_b=b,
            co_change_count=count,
            total_a=total_a,
            total_b=total_b,
            jaccard=round(jaccard, 3),
        ))

    # Sort by Jaccard descending
    pairs.sort(key=lambda p: (-p.jaccard, -p.co_change_count))

    # Optionally check import links
    if check_imports and pairs:
        pairs = _annotate_import_links(repo_path, pairs)

    return CoChangeReport(
        pairs=pairs,
        commits_analyzed=len(commit_sets),
        files_analyzed=len(file_counts),
        threshold=threshold,
    )


def _annotate_import_links(
    repo_path: str,
    pairs: list[CoChangePair],
) -> list[CoChangePair]:
    """Check each pair for direct import relationships via the dependency graph."""
    try:
        from .graph import build_graph_v2
        graph = build_graph_v2(str(Path(repo_path).resolve()))
    except Exception:
        logger.debug("Could not build graph for import checking", exc_info=True)
        return pairs

    annotated: list[CoChangePair] = []
    for p in pairs:
        deps_a = set(graph.get_dependencies(p.file_a))
        deps_b = set(graph.get_dependencies(p.file_b))
        has_link = p.file_b in deps_a or p.file_a in deps_b

        annotated.append(CoChangePair(
            file_a=p.file_a,
            file_b=p.file_b,
            co_change_count=p.co_change_count,
            total_a=p.total_a,
            total_b=p.total_b,
            jaccard=p.jaccard,
            has_import_link=has_link,
        ))

    return annotated


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


def format_co_changes(report: CoChangeReport) -> str:
    """Format co-change report as human-readable text."""
    lines: list[str] = []
    lines.append("## Co-Change Analysis")
    lines.append(f"**Commits analyzed**: {report.commits_analyzed}")
    lines.append(f"**Files analyzed**: {report.files_analyzed}")
    lines.append(f"**Threshold**: {report.threshold}")
    lines.append(f"**Pairs found**: {len(report.pairs)}")
    lines.append("")

    if not report.pairs:
        lines.append("No co-change pairs found above threshold.")
        return "\n".join(lines)

    # Table header
    lines.append("| File A | File B | Co-changes | Jaccard | Import Link | Confidence |")
    lines.append("|--------|--------|:----------:|:-------:|:-----------:|:----------:|")

    for p in report.pairs:
        import_str = "—"
        if p.has_import_link is True:
            import_str = "yes"
        elif p.has_import_link is False:
            import_str = "**NO**"

        lines.append(
            f"| `{p.file_a}` | `{p.file_b}` | {p.co_change_count} | "
            f"{p.jaccard:.2f} | {import_str} | {p.confidence} |"
        )

    # Highlight hidden coupling
    hidden = report.hidden_coupling
    if hidden:
        lines.append("")
        lines.append(f"### Hidden Coupling ({len(hidden)} pairs)")
        lines.append("These files change together but have NO import relationship:")
        for p in hidden:
            lines.append(f"- `{p.file_a}` ↔ `{p.file_b}` (Jaccard: {p.jaccard:.2f})")

    return "\n".join(lines)
