"""
dead_code.py — Graph-based dead code detection.

Pure graph-traversal approach: finds exported symbols with zero dependents
(no other file imports them). No LLM needed.

Uses the file-level dependency graph to identify:
  1. Isolated modules — files with no incoming edges (nobody imports them)
  2. Dead exports — symbols exported by a module but never imported anywhere

Entry points:
  - detect_dead_code(repo_path): full analysis
  - format_dead_code_report(report): human-readable output
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from .graph import CodeGraph, Node, build_graph_v2, is_test_file

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DeadSymbol:
    """A potentially dead exported symbol."""

    name: str
    kind: str  # function, class, variable, etc.
    file: str
    confidence: str  # high, medium, low


@dataclass
class DeadCodeReport:
    """Full dead code analysis result."""

    isolated_modules: list[str] = field(default_factory=list)
    """Files with zero dependents (nobody imports them)."""

    dead_symbols: list[DeadSymbol] = field(default_factory=list)
    """Exported symbols that no other file references."""

    entry_points: list[str] = field(default_factory=list)
    """Files detected as entry points (excluded from dead code)."""

    total_modules: int = 0
    """Total modules analyzed."""

    total_exports: int = 0
    """Total exported symbols analyzed."""


# ---------------------------------------------------------------------------
# Entry point detection
# ---------------------------------------------------------------------------

# Patterns that indicate a file is an entry point (not dead just because
# nobody imports it internally).
_ENTRY_POINT_PATTERNS = (
    "__main__",
    "main.py",
    "cli.py",
    "app.py",
    "server.py",
    "index.ts",
    "index.js",
    "index.tsx",
    "index.jsx",
    "main.go",
    "main.rs",
    "setup.py",
    "pyproject.toml",
    "conftest.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
)

_INIT_PATTERNS = (
    "__init__.py",
    "mod.rs",
)


def _is_entry_point(file_path: str) -> bool:
    """Check if a file is likely an entry point or config file."""
    name = Path(file_path).name
    return (
        name in _ENTRY_POINT_PATTERNS
        or name in _INIT_PATTERNS
        or is_test_file(file_path)
    )


# ---------------------------------------------------------------------------
# Core detection
# ---------------------------------------------------------------------------


def _build_import_index(graph: CodeGraph) -> dict[str, set[str]]:
    """Build a reverse index: target_file → set of files that import it."""
    index: dict[str, set[str]] = {}
    for edge in graph.edges:
        if edge.edge_type in ("imports", "depends_on"):
            index.setdefault(edge.target, set()).add(edge.source)
    return index


def _build_export_usage_index(
    root: Path,
    graph: CodeGraph,
) -> dict[str, set[str]]:
    """Build index of which export names are actually referenced by importers.

    Returns: export_name → set of files that reference it.
    """
    from .extractors import get_extractor

    usage: dict[str, set[str]] = {}

    for node in graph.nodes:
        if node.node_type != "module":
            continue

        abs_path = root / node.file_path
        if not abs_path.exists():
            continue

        extractor = get_extractor(node.file_path)
        if not extractor:
            continue

        try:
            content = abs_path.read_text(errors="replace")
        except OSError:
            continue

        imports = extractor.extract_imports(content)
        for imp in imports:
            for sym_name in imp.symbols:
                usage.setdefault(sym_name, set()).add(node.file_path)

    return usage


def detect_dead_code(
    repo_path: str,
    *,
    include_tests: bool = False,
    files: list[str] | None = None,
) -> DeadCodeReport:
    """Detect potentially dead code using graph analysis.

    Args:
        repo_path: Path to the repository root.
        include_tests: Whether to analyze test files (default False).
        files: Optional file list. If None, auto-discovers.

    Returns:
        DeadCodeReport with isolated modules and dead symbols.
    """
    root = Path(repo_path).resolve()
    graph = build_graph_v2(str(root), files)

    module_nodes = [n for n in graph.nodes if n.node_type == "module"]
    import_index = _build_import_index(graph)
    export_usage = _build_export_usage_index(root, graph)

    entry_points: list[str] = []
    isolated: list[str] = []
    dead_symbols: list[DeadSymbol] = []
    total_exports = 0

    for node in module_nodes:
        fp = node.file_path

        # Skip test files unless explicitly included
        if not include_tests and is_test_file(fp):
            continue

        # Detect entry points
        if _is_entry_point(fp):
            entry_points.append(fp)
            continue

        # Check if anyone imports this file
        importers = import_index.get(fp, set())
        if not importers:
            isolated.append(fp)

        # Check each export
        for export_name in node.exports:
            total_exports += 1
            # Is this export referenced by any file?
            referencing_files = export_usage.get(export_name, set())
            # Exclude self-references
            external_refs = referencing_files - {fp}

            if not external_refs:
                # Determine confidence based on context
                if not importers:
                    confidence = "high"
                elif export_name.startswith("_"):
                    confidence = "low"  # private by convention
                else:
                    confidence = "medium"

                dead_symbols.append(DeadSymbol(
                    name=export_name,
                    kind=_guess_kind(export_name),
                    file=fp,
                    confidence=confidence,
                ))

    # Filter isolated: don't count files that are entry points
    entry_set = set(entry_points)
    isolated = [f for f in isolated if f not in entry_set]

    return DeadCodeReport(
        isolated_modules=sorted(isolated),
        dead_symbols=sorted(dead_symbols, key=lambda s: (s.confidence, s.file, s.name)),
        entry_points=sorted(entry_points),
        total_modules=len(module_nodes),
        total_exports=total_exports,
    )


def _guess_kind(name: str) -> str:
    """Guess the kind of a symbol from its name."""
    if name[0].isupper():
        return "class"
    return "function"


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


def format_dead_code_report(report: DeadCodeReport) -> str:
    """Format a dead code report as human-readable markdown."""
    lines: list[str] = []

    lines.append("## Dead Code Analysis")
    lines.append("")
    lines.append(f"**Modules analyzed**: {report.total_modules}")
    lines.append(f"**Exports analyzed**: {report.total_exports}")
    lines.append(f"**Isolated modules**: {len(report.isolated_modules)}")
    lines.append(f"**Dead symbols**: {len(report.dead_symbols)}")
    lines.append(f"**Entry points (excluded)**: {len(report.entry_points)}")
    lines.append("")

    if report.isolated_modules:
        lines.append("### Isolated Modules (no incoming imports)")
        lines.append("")
        for f in report.isolated_modules:
            lines.append(f"- `{f}`")
        lines.append("")

    if report.dead_symbols:
        # Group by confidence
        by_confidence: dict[str, list[DeadSymbol]] = {}
        for sym in report.dead_symbols:
            by_confidence.setdefault(sym.confidence, []).append(sym)

        for confidence in ("high", "medium", "low"):
            syms = by_confidence.get(confidence, [])
            if not syms:
                continue

            lines.append(f"### Dead Symbols — {confidence} confidence")
            lines.append("")
            for sym in syms:
                lines.append(f"- `{sym.file}` — {sym.kind} **{sym.name}**")
            lines.append("")

    if not report.isolated_modules and not report.dead_symbols:
        lines.append("No dead code detected.")
        lines.append("")

    return "\n".join(lines)
