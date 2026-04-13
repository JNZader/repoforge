"""Change-impact analysis — identify which tests need to run for a change.

Given changed files (from a commit or file list), maps each changed file
to the test files that exercise it. Uses two strategies:

1. **Graph-based**: Build dependency graph, find test files that transitively
   import changed code (via build_graph_v2 + is_test_file).

2. **Naming convention**: Match test files by naming patterns:
   - `src/auth.py` → `tests/test_auth.py`
   - `src/services/user.ts` → `src/services/user.test.ts`
   - `pkg/handler.go` → `pkg/handler_test.go`

Combines both strategies and deduplicates.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .graph import CodeGraph, build_graph_v2, get_blast_radius_v2, is_test_file

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class SourceTestMapping:
    """Maps a source file to its affected tests."""

    source_file: str
    """The changed source file."""

    graph_tests: list[str] = field(default_factory=list)
    """Tests found via dependency graph traversal."""

    convention_tests: list[str] = field(default_factory=list)
    """Tests found via naming convention matching."""

    @property
    def all_tests(self) -> list[str]:
        """All unique tests from both strategies, sorted."""
        return sorted(set(self.graph_tests + self.convention_tests))


@dataclass
class ChangeImpactReport:
    """Full change-impact analysis result."""

    changed_files: list[str] = field(default_factory=list)
    """Files that changed."""

    mappings: list[SourceTestMapping] = field(default_factory=list)
    """Per-file test mappings."""

    commit: str | None = None
    """Commit SHA if triggered by a commit."""

    @property
    def all_tests(self) -> list[str]:
        """All unique test files that should be run."""
        tests: set[str] = set()
        for m in self.mappings:
            tests.update(m.all_tests)
        return sorted(tests)

    @property
    def untested_files(self) -> list[str]:
        """Changed files with no mapped tests."""
        return [
            m.source_file for m in self.mappings
            if not m.all_tests
        ]


# ---------------------------------------------------------------------------
# Naming convention matching
# ---------------------------------------------------------------------------


def _find_convention_tests(
    source_file: str,
    all_files: set[str],
) -> list[str]:
    """Find test files matching naming conventions for a source file."""
    p = Path(source_file)
    stem = p.stem
    suffix = p.suffix
    parent = str(p.parent)

    candidates: list[str] = []

    if suffix == ".py":
        # Python: test_foo.py, foo_test.py, tests/test_foo.py
        candidates.extend([
            f"{parent}/test_{stem}.py",
            f"{parent}/{stem}_test.py",
            f"tests/test_{stem}.py",
            f"tests/{parent}/test_{stem}.py",
        ])
    elif suffix in (".ts", ".tsx", ".js", ".jsx"):
        # JS/TS: foo.test.ts, foo.spec.ts
        base = stem.rsplit(".", 1)[0] if "." in stem else stem
        for ext in (suffix, ):
            candidates.extend([
                f"{parent}/{base}.test{ext}",
                f"{parent}/{base}.spec{ext}",
                f"{parent}/__tests__/{base}.test{ext}",
                f"{parent}/__tests__/{base}.spec{ext}",
            ])
    elif suffix == ".go":
        # Go: foo_test.go (same directory)
        candidates.append(f"{parent}/{stem}_test.go")
    elif suffix == ".java":
        # Java: FooTest.java, FooTests.java
        candidates.extend([
            f"{parent}/{stem}Test.java",
            f"{parent}/{stem}Tests.java",
        ])
        # Also check test mirror directory
        test_parent = parent.replace("src/main", "src/test", 1)
        if test_parent != parent:
            candidates.extend([
                f"{test_parent}/{stem}Test.java",
                f"{test_parent}/{stem}Tests.java",
            ])
    elif suffix == ".rs":
        candidates.append(f"{parent}/{stem}_test.rs")
        candidates.append(f"tests/{stem}.rs")

    # Normalize paths and check existence
    found: list[str] = []
    for c in candidates:
        # Normalize: remove leading ./ and double slashes
        normalized = str(Path(c))
        if normalized in all_files:
            found.append(normalized)

    return found


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_changed_files(repo_path: str, commit: str) -> list[str]:
    """Get changed files from a commit."""
    repo = str(Path(repo_path).resolve())
    try:
        if ".." in commit:
            ref_spec = commit
        else:
            ref_spec = f"{commit}~1..{commit}"

        result = subprocess.run(
            ["git", "-C", repo, "diff", "--name-only", ref_spec],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return [f for f in result.stdout.strip().splitlines() if f]
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("git diff failed for %s", commit)
    return []


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------


def analyze_change_impact(
    repo_path: str,
    files: list[str] | None = None,
    commit: str | None = None,
) -> ChangeImpactReport:
    """Analyze which tests need to run for a set of changes.

    Provide either ``files`` (list of relative paths) or ``commit`` (git ref).

    Args:
        repo_path: Path to the repository root.
        files: List of changed file paths (relative to repo root).
        commit: Git commit SHA or range.

    Returns:
        ChangeImpactReport with test mappings for each changed file.
    """
    root = str(Path(repo_path).resolve())

    # Resolve changed files
    if commit and not files:
        changed = _get_changed_files(root, commit)
    elif files:
        changed = list(files)
    else:
        return ChangeImpactReport()

    # Filter out test files from changed list (they ARE tests, not sources)
    source_files = [f for f in changed if not is_test_file(f)]
    changed_tests = [f for f in changed if is_test_file(f)]

    if not source_files:
        # Only test files changed — they test themselves
        return ChangeImpactReport(
            changed_files=changed,
            mappings=[],
            commit=commit,
        )

    # Build dependency graph
    graph = build_graph_v2(root)

    # Collect all file paths in the graph for convention matching
    all_graph_files = {n.id for n in graph.nodes if n.node_type == "module"}

    # Analyze each changed source file
    mappings: list[SourceTestMapping] = []

    for source_file in source_files:
        # Strategy 1: Graph-based — find test files in blast radius
        br = get_blast_radius_v2(
            graph, source_file,
            max_depth=3,
            max_files=50,
            include_tests=True,
        )
        graph_tests = list(br.test_files)

        # Strategy 2: Naming convention
        convention_tests = _find_convention_tests(source_file, all_graph_files)

        mappings.append(SourceTestMapping(
            source_file=source_file,
            graph_tests=graph_tests,
            convention_tests=convention_tests,
        ))

    return ChangeImpactReport(
        changed_files=changed,
        mappings=mappings,
        commit=commit,
    )


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


def format_change_impact(report: ChangeImpactReport) -> str:
    """Format a change-impact report as human-readable text."""
    lines: list[str] = []

    if report.commit:
        lines.append(f"## Change Impact: commit {report.commit}")
    else:
        lines.append("## Change Impact Analysis")

    lines.append(f"**Changed files**: {len(report.changed_files)}")
    lines.append(f"**Tests to run**: {len(report.all_tests)}")

    if report.untested_files:
        lines.append(f"**Untested files**: {len(report.untested_files)}")
    lines.append("")

    if report.all_tests:
        lines.append("### Tests to run")
        for t in report.all_tests:
            lines.append(f"- `{t}`")
        lines.append("")

    if report.mappings:
        lines.append("### Per-file mapping")
        for m in report.mappings:
            tests = m.all_tests
            if tests:
                lines.append(f"- `{m.source_file}` → {len(tests)} test(s)")
                for t in tests:
                    strategy = []
                    if t in m.graph_tests:
                        strategy.append("graph")
                    if t in m.convention_tests:
                        strategy.append("convention")
                    lines.append(f"  - `{t}` ({', '.join(strategy)})")
            else:
                lines.append(f"- `{m.source_file}` → **no tests found**")
        lines.append("")

    if report.untested_files:
        lines.append("### ⚠ Untested changed files")
        for f in report.untested_files:
            lines.append(f"- `{f}`")
        lines.append("")

    return "\n".join(lines)
