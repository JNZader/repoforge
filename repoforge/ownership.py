"""Ownership and bus-factor analysis from git history.

Computes per-file and per-directory ownership concentration using git log.
Flags bus-factor risks where a single author owns >80% of a file/module.

Metrics:
  - **Top contributor**: Who wrote most lines (by commit count or line changes)
  - **Ownership ratio**: Top contributor's share of total commits
  - **Bus factor**: Number of contributors needed to cover 50% of commits
  - **Risk level**: Based on bus factor (1 = critical, 2 = warning, 3+ = ok)

Uses git log (not git blame) for speed — counts commits per author per file.
"""

from __future__ import annotations

import logging
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class FileOwnership:
    """Ownership data for a single file."""

    file: str
    """Relative file path."""

    contributors: dict[str, int] = field(default_factory=dict)
    """Author → commit count mapping."""

    total_commits: int = 0
    """Total commits touching this file."""

    @property
    def top_contributor(self) -> str | None:
        """Author with the most commits."""
        if not self.contributors:
            return None
        return max(self.contributors, key=self.contributors.get)  # type: ignore[arg-type]

    @property
    def ownership_ratio(self) -> float:
        """Top contributor's share (0.0-1.0)."""
        if not self.contributors or self.total_commits == 0:
            return 0.0
        top_count = max(self.contributors.values())
        return top_count / self.total_commits

    @property
    def bus_factor(self) -> int:
        """Number of contributors needed to cover 50% of commits.

        A bus factor of 1 means a single person wrote >50% — risky.
        """
        if not self.contributors:
            return 0

        sorted_counts = sorted(self.contributors.values(), reverse=True)
        target = self.total_commits * 0.5
        cumulative = 0
        for i, count in enumerate(sorted_counts, 1):
            cumulative += count
            if cumulative >= target:
                return i
        return len(sorted_counts)

    @property
    def risk_level(self) -> str:
        """Risk assessment based on bus factor."""
        bf = self.bus_factor
        if bf <= 1:
            return "critical"
        if bf == 2:
            return "warning"
        return "ok"


@dataclass
class DirectoryOwnership:
    """Aggregated ownership for a directory/module."""

    directory: str
    """Directory path."""

    contributors: dict[str, int] = field(default_factory=dict)
    """Author → total commit count across all files in this dir."""

    file_count: int = 0
    """Number of files in this directory."""

    total_commits: int = 0
    """Total commits across all files."""

    @property
    def top_contributor(self) -> str | None:
        if not self.contributors:
            return None
        return max(self.contributors, key=self.contributors.get)  # type: ignore[arg-type]

    @property
    def ownership_ratio(self) -> float:
        if not self.contributors or self.total_commits == 0:
            return 0.0
        top_count = max(self.contributors.values())
        return top_count / self.total_commits

    @property
    def bus_factor(self) -> int:
        if not self.contributors:
            return 0
        sorted_counts = sorted(self.contributors.values(), reverse=True)
        target = self.total_commits * 0.5
        cumulative = 0
        for i, count in enumerate(sorted_counts, 1):
            cumulative += count
            if cumulative >= target:
                return i
        return len(sorted_counts)

    @property
    def risk_level(self) -> str:
        bf = self.bus_factor
        if bf <= 1:
            return "critical"
        if bf == 2:
            return "warning"
        return "ok"


@dataclass
class OwnershipReport:
    """Full ownership analysis result."""

    files: list[FileOwnership] = field(default_factory=list)
    """Per-file ownership data."""

    directories: list[DirectoryOwnership] = field(default_factory=list)
    """Per-directory aggregated ownership."""

    total_contributors: int = 0
    """Unique contributors across the repo."""

    total_files: int = 0
    """Total files analyzed."""

    @property
    def bus_factor_risks(self) -> list[FileOwnership]:
        """Files with bus factor = 1 (critical risk)."""
        return [f for f in self.files if f.bus_factor <= 1 and f.total_commits >= 3]

    @property
    def directory_risks(self) -> list[DirectoryOwnership]:
        """Directories with bus factor = 1 (critical risk)."""
        return [d for d in self.directories if d.bus_factor <= 1 and d.total_commits >= 3]


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_file_authors(
    repo_path: str,
    max_commits: int = 1000,
    since: str | None = None,
) -> dict[str, dict[str, int]]:
    """Extract per-file author commit counts from git log.

    Returns: {file_path: {author: commit_count}}.
    """
    repo = str(Path(repo_path).resolve())
    cmd = [
        "git", "-C", repo, "log",
        "--name-only",
        "--pretty=format:---AUTHOR---%an",
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
            return {}
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("git log failed")
        return {}

    file_authors: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    current_author = ""

    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("---AUTHOR---"):
            current_author = line[len("---AUTHOR---"):]
        elif line and current_author:
            file_authors[line][current_author] += 1

    return dict(file_authors)


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------


def analyze_ownership(
    repo_path: str,
    *,
    max_commits: int = 1000,
    since: str | None = None,
    bus_factor_only: bool = False,
) -> OwnershipReport:
    """Analyze file and directory ownership from git history.

    Args:
        repo_path: Path to the repository root.
        max_commits: Maximum commits to analyze.
        since: Git date filter (e.g., "1 year ago").
        bus_factor_only: If True, only include files with bus factor <= 2.

    Returns:
        OwnershipReport with per-file and per-directory data.
    """
    file_authors = _get_file_authors(repo_path, max_commits=max_commits, since=since)

    if not file_authors:
        return OwnershipReport()

    # Build per-file ownership
    all_contributors: set[str] = set()
    files: list[FileOwnership] = []

    for file_path, authors in sorted(file_authors.items()):
        total = sum(authors.values())
        all_contributors.update(authors.keys())

        fo = FileOwnership(
            file=file_path,
            contributors=dict(authors),
            total_commits=total,
        )

        if bus_factor_only and fo.bus_factor > 2:
            continue

        files.append(fo)

    # Aggregate per-directory
    dir_data: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    dir_files: dict[str, int] = defaultdict(int)
    dir_commits: dict[str, int] = defaultdict(int)

    for fo in files:
        directory = str(Path(fo.file).parent)
        if directory == ".":
            directory = "(root)"
        dir_files[directory] += 1
        dir_commits[directory] += fo.total_commits
        for author, count in fo.contributors.items():
            dir_data[directory][author] += count

    directories: list[DirectoryOwnership] = []
    for directory in sorted(dir_data.keys()):
        do = DirectoryOwnership(
            directory=directory,
            contributors=dict(dir_data[directory]),
            file_count=dir_files[directory],
            total_commits=dir_commits[directory],
        )
        if bus_factor_only and do.bus_factor > 2:
            continue
        directories.append(do)

    return OwnershipReport(
        files=files,
        directories=directories,
        total_contributors=len(all_contributors),
        total_files=len(files),
    )


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


def format_ownership(report: OwnershipReport, *, bus_factor: bool = False) -> str:
    """Format ownership report as human-readable text."""
    lines: list[str] = []
    lines.append("## Ownership Analysis")
    lines.append(f"**Total contributors**: {report.total_contributors}")
    lines.append(f"**Files analyzed**: {report.total_files}")
    lines.append("")

    # Directory summary
    if report.directories:
        lines.append("### Directory Ownership")
        lines.append(
            "| Directory | Files | Commits | Top Contributor | Ownership | "
            "Bus Factor | Risk |"
        )
        lines.append(
            "|-----------|:-----:|:-------:|-----------------|:---------:|"
            ":----------:|:----:|"
        )

        for d in report.directories:
            top = d.top_contributor or "—"
            lines.append(
                f"| `{d.directory}` | {d.file_count} | {d.total_commits} | "
                f"{top} | {d.ownership_ratio:.0%} | {d.bus_factor} | "
                f"{d.risk_level} |"
            )
        lines.append("")

    # Bus factor risks
    if bus_factor:
        risks = report.bus_factor_risks
        if risks:
            lines.append(f"### Bus Factor Risks ({len(risks)} files)")
            lines.append("Files where a single contributor owns >50% of commits:")
            lines.append("")
            lines.append(
                "| File | Top Contributor | Ownership | Commits | Risk |"
            )
            lines.append(
                "|------|-----------------|:---------:|:-------:|:----:|"
            )

            for f in sorted(risks, key=lambda x: -x.ownership_ratio):
                top = f.top_contributor or "—"
                lines.append(
                    f"| `{f.file}` | {top} | {f.ownership_ratio:.0%} | "
                    f"{f.total_commits} | {f.risk_level} |"
                )
            lines.append("")
        else:
            lines.append("### Bus Factor: No Critical Risks Found")
            lines.append("No files with bus factor ≤ 1 and ≥ 3 commits.")
            lines.append("")

        dir_risks = report.directory_risks
        if dir_risks:
            lines.append(f"### Module-Level Bus Factor Risks ({len(dir_risks)} directories)")
            for d in sorted(dir_risks, key=lambda x: -x.ownership_ratio):
                top = d.top_contributor or "—"
                lines.append(
                    f"- `{d.directory}/` — **{top}** owns {d.ownership_ratio:.0%} "
                    f"({d.total_commits} commits, {d.file_count} files)"
                )
            lines.append("")

    return "\n".join(lines)
