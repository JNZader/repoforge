"""Blast-radius module — compute transitive impact of changes.

Given a commit or list of files, builds a file-level dependency graph
(using the existing build_graph_v2 infrastructure) and computes which
files/functions are transitively affected.

Two entry points:
  - blast_radius_from_commit(repo, commit): get changed files from git, then compute
  - blast_radius_from_files(repo, files): compute directly from file list

Both return a BlastRadiusReport with affected files, test files, and risk level.

Optionally uses tree-sitter AST (via intelligence/ extractors) for finer-grained
symbol-level analysis when the ``intelligence`` extra is installed.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .graph import BlastRadiusResult, CodeGraph, build_graph_v2, get_blast_radius_v2, is_test_file

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ASTSymbolInfo:
    """A symbol extracted via tree-sitter (optional enrichment)."""

    name: str
    kind: str  # function, class, method
    file: str
    line: int = 0
    signature: str = ""


@dataclass
class BlastRadiusReport:
    """Full blast-radius analysis result."""

    changed_files: list[str] = field(default_factory=list)
    """Files that were changed (input)."""

    affected_files: list[str] = field(default_factory=list)
    """Non-test files transitively affected by the change."""

    affected_tests: list[str] = field(default_factory=list)
    """Test files that should be verified."""

    depth: int = 0
    """Max BFS depth reached."""

    exceeded_cap: bool = False
    """True if result was truncated by max_files."""

    symbols: list[ASTSymbolInfo] = field(default_factory=list)
    """Optional: symbols defined in changed files (tree-sitter enrichment)."""

    commit: str | None = None
    """Commit SHA if analysis was triggered by a commit."""

    @property
    def total_affected(self) -> int:
        return len(self.affected_files) + len(self.affected_tests)

    @property
    def risk_level(self) -> str:
        n = self.total_affected
        if n == 0:
            return "safe"
        if n <= 3:
            return "low"
        if n <= 10:
            return "medium"
        return "high"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_changed_files_from_commit(repo_path: str, commit: str) -> list[str]:
    """Get files changed in a commit (or between commit and HEAD)."""
    repo = str(Path(repo_path).resolve())
    try:
        # If it looks like a range (a..b), use it directly
        if ".." in commit:
            ref_spec = commit
        else:
            # Single commit: diff against its parent
            ref_spec = f"{commit}~1..{commit}"

        result = subprocess.run(
            ["git", "-C", repo, "diff", "--name-only", ref_spec],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return [f for f in result.stdout.strip().splitlines() if f]
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("git diff failed for commit %s", commit)

    return []


def _get_changed_files_working_tree(repo_path: str) -> list[str]:
    """Get files changed in the working tree (staged + unstaged)."""
    repo = str(Path(repo_path).resolve())
    files: set[str] = set()
    try:
        # Staged changes
        result = subprocess.run(
            ["git", "-C", repo, "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            files.update(f for f in result.stdout.strip().splitlines() if f)

        # Unstaged changes
        result = subprocess.run(
            ["git", "-C", repo, "diff", "--name-only"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            files.update(f for f in result.stdout.strip().splitlines() if f)
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("git diff failed for working tree")

    return sorted(files)


# ---------------------------------------------------------------------------
# Tree-sitter enrichment (optional)
# ---------------------------------------------------------------------------


def _extract_ast_symbols(repo_path: str, files: list[str]) -> list[ASTSymbolInfo]:
    """Try to extract symbols via tree-sitter. Returns empty list if unavailable."""
    try:
        from .intelligence.ast_extractor import ASTSymbol
        from .intelligence.extractor_registry import get_ast_extractor
    except ImportError:
        logger.debug("tree-sitter not available, skipping AST enrichment")
        return []

    root = Path(repo_path).resolve()
    symbols: list[ASTSymbolInfo] = []

    for file_path in files:
        abs_path = root / file_path
        if not abs_path.exists():
            continue

        try:
            content = abs_path.read_text(errors="replace")
        except OSError:
            continue

        extractor = get_ast_extractor(file_path)
        if extractor is None:
            continue

        try:
            ast_symbols = extractor.extract_symbols(content, file_path)
            for sym in ast_symbols:
                symbols.append(ASTSymbolInfo(
                    name=sym.name,
                    kind=sym.kind,
                    file=file_path,
                    line=sym.line,
                    signature=sym.signature,
                ))
        except Exception:
            logger.debug("AST extraction failed for %s", file_path, exc_info=True)

    return symbols


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------


def _compute_blast_radius(
    repo_path: str,
    changed_files: list[str],
    *,
    max_depth: int = 3,
    max_files: int = 50,
    include_tests: bool = True,
    with_ast: bool = False,
) -> BlastRadiusReport:
    """Shared implementation: build graph, compute blast radius for each changed file."""
    root = str(Path(repo_path).resolve())

    # Build the full dependency graph
    graph = build_graph_v2(root)

    # Accumulate blast radius across all changed files
    all_affected: set[str] = set()
    all_tests: set[str] = set()
    max_depth_reached = 0
    exceeded = False

    for file_path in changed_files:
        br = get_blast_radius_v2(
            graph, file_path,
            max_depth=max_depth,
            max_files=max_files,
            include_tests=include_tests,
        )
        all_affected.update(br.files)
        all_tests.update(br.test_files)
        max_depth_reached = max(max_depth_reached, br.depth)
        if br.exceeded_cap:
            exceeded = True

    # Remove changed files from affected (they are the cause, not the effect)
    changed_set = set(changed_files)
    all_affected -= changed_set
    all_tests -= changed_set

    # Optional AST enrichment
    symbols: list[ASTSymbolInfo] = []
    if with_ast:
        symbols = _extract_ast_symbols(root, changed_files)

    return BlastRadiusReport(
        changed_files=sorted(changed_files),
        affected_files=sorted(all_affected),
        affected_tests=sorted(all_tests),
        depth=max_depth_reached,
        exceeded_cap=exceeded,
        symbols=symbols,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def blast_radius_from_commit(
    repo_path: str,
    commit: str,
    *,
    max_depth: int = 3,
    max_files: int = 50,
    include_tests: bool = True,
    with_ast: bool = False,
) -> BlastRadiusReport:
    """Compute blast radius from a git commit.

    Args:
        repo_path: Path to the repository root.
        commit: Git commit SHA, range (a..b), or ref name.
        max_depth: Max BFS depth for transitive deps.
        max_files: Cap on total affected files.
        include_tests: Whether to include test files.
        with_ast: Whether to enrich with tree-sitter symbols.

    Returns:
        BlastRadiusReport with all affected files and optional symbols.
    """
    changed = _get_changed_files_from_commit(repo_path, commit)
    if not changed:
        return BlastRadiusReport(commit=commit)

    report = _compute_blast_radius(
        repo_path, changed,
        max_depth=max_depth,
        max_files=max_files,
        include_tests=include_tests,
        with_ast=with_ast,
    )
    report.commit = commit
    return report


def blast_radius_from_files(
    repo_path: str,
    files: list[str],
    *,
    max_depth: int = 3,
    max_files: int = 50,
    include_tests: bool = True,
    with_ast: bool = False,
) -> BlastRadiusReport:
    """Compute blast radius from a list of file paths.

    Args:
        repo_path: Path to the repository root.
        files: List of relative file paths that changed.
        max_depth: Max BFS depth for transitive deps.
        max_files: Cap on total affected files.
        include_tests: Whether to include test files.
        with_ast: Whether to enrich with tree-sitter symbols.

    Returns:
        BlastRadiusReport with all affected files and optional symbols.
    """
    if not files:
        return BlastRadiusReport()

    return _compute_blast_radius(
        repo_path, files,
        max_depth=max_depth,
        max_files=max_files,
        include_tests=include_tests,
        with_ast=with_ast,
    )


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_blast_radius(report: BlastRadiusReport) -> str:
    """Format a blast radius report as human-readable text."""
    lines: list[str] = []

    if report.commit:
        lines.append(f"## Blast Radius: commit {report.commit}")
    else:
        lines.append("## Blast Radius Analysis")

    lines.append(f"**Risk level**: {report.risk_level}")
    lines.append(f"**Changed files**: {len(report.changed_files)}")
    lines.append(f"**Affected files**: {len(report.affected_files)}")
    lines.append(f"**Affected tests**: {len(report.affected_tests)}")
    lines.append(f"**Max depth**: {report.depth}")
    if report.exceeded_cap:
        lines.append("**Warning**: Result was truncated (exceeded file cap)")
    lines.append("")

    if report.changed_files:
        lines.append("### Changed files")
        for f in report.changed_files:
            lines.append(f"- `{f}`")
        lines.append("")

    if report.affected_files:
        lines.append("### Affected files (transitive dependents)")
        for f in report.affected_files:
            lines.append(f"- `{f}`")
        lines.append("")

    if report.affected_tests:
        lines.append("### Test files to verify")
        for f in report.affected_tests:
            lines.append(f"- `{f}`")
        lines.append("")

    if report.symbols:
        lines.append("### Symbols in changed files (AST)")
        for sym in report.symbols:
            lines.append(f"- `{sym.file}:{sym.line}` {sym.kind} **{sym.name}**")
            if sym.signature:
                lines.append(f"  `{sym.signature}`")
        lines.append("")

    if not report.affected_files and not report.affected_tests:
        lines.append("No downstream dependencies found — changes are isolated.")
        lines.append("")

    return "\n".join(lines)
