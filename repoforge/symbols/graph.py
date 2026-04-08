"""
Symbol Graph — call-level dependency graph between functions/classes.

Builds a graph where nodes are symbols (functions, classes) and edges
represent call relationships. Supports both intra-file and cross-file
call resolution via import analysis.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .extractor import (
    _CALL_RE,
    SKIP_NAMES,
    Symbol,
    detect_language,
    extract_symbols,
)
from .index import SymbolIndex

logger = logging.getLogger(__name__)

# Confidence ordering: higher index = higher confidence.
CONFIDENCE_ORDER: dict[str, int] = {
    "heuristic": 0,
    "linked": 1,
    "imported": 2,
    "direct": 3,
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CallEdge:
    """A directed call relationship between two symbols."""

    caller: str
    """Caller symbol id (file::name)."""

    callee: str
    """Callee symbol id (file::name)."""

    confidence: str = "direct"
    """Resolution confidence: 'direct' | 'imported' | 'heuristic' | 'linked'."""


@dataclass
class SymbolGraph:
    """Graph of symbol-level call dependencies."""

    symbols: dict[str, Symbol] = field(default_factory=dict)
    """symbol_id → Symbol mapping."""

    edges: list[CallEdge] = field(default_factory=list)
    """Directed call edges."""

    def add_symbol(self, symbol: Symbol) -> None:
        """Add a symbol to the graph (dedup by id)."""
        self.symbols[symbol.id] = symbol

    def add_edge(self, edge: CallEdge) -> None:
        """Add a call edge (dedup by caller+callee)."""
        for existing in self.edges:
            if existing.caller == edge.caller and existing.callee == edge.callee:
                return
        self.edges.append(edge)

    def get_callees(self, symbol_id: str) -> list[str]:
        """Get symbols called by this symbol."""
        return [e.callee for e in self.edges if e.caller == symbol_id]

    def get_callers(self, symbol_id: str) -> list[str]:
        """Get symbols that call this symbol."""
        return [e.caller for e in self.edges if e.callee == symbol_id]

    def filter_edges(self, min_confidence: str = "heuristic") -> "SymbolGraph":
        """Return a new SymbolGraph with only edges at or above *min_confidence*.

        Confidence ordering (high to low): direct > imported > linked > heuristic.
        All symbols are preserved; only edges are filtered.

        Args:
            min_confidence: Minimum confidence level to keep. Defaults to
                ``"heuristic"`` (keep everything).

        Returns:
            New :class:`SymbolGraph` instance with the filtered edge set.
        """
        threshold = CONFIDENCE_ORDER.get(min_confidence, 0)
        filtered = [
            e for e in self.edges
            if CONFIDENCE_ORDER.get(e.confidence, 0) >= threshold
        ]
        new_graph = SymbolGraph(
            symbols=dict(self.symbols),
            edges=filtered,
        )
        return new_graph

    def to_json(self) -> str:
        """Export as JSON (symbols + edges arrays, D3/Cytoscape-compatible).

        Returns:
            JSON string with ``symbols`` and ``edges`` arrays.
        """
        data = {
            "symbols": [
                {
                    "id": s.id,
                    "name": s.name,
                    "kind": s.kind,
                    "file": s.file,
                    "line": s.line,
                    "end_line": s.end_line,
                }
                for s in self.symbols.values()
            ],
            "edges": [
                {"caller": e.caller, "callee": e.callee, "confidence": e.confidence}
                for e in self.edges
            ],
        }
        return json.dumps(data, indent=2) + "\n"

    def summary(self) -> str:
        """Human-readable summary: symbol count, edge count, most-called.

        Returns:
            Multi-line summary string.
        """
        functions = [s for s in self.symbols.values() if s.kind == "function"]
        classes = [s for s in self.symbols.values() if s.kind == "class"]
        files = {s.file for s in self.symbols.values()}

        # Count incoming calls per symbol (most-called)
        call_count: dict[str, int] = defaultdict(int)
        for e in self.edges:
            call_count[e.callee] += 1

        sorted_callees = sorted(call_count.items(), key=lambda x: x[1], reverse=True)
        top = sorted_callees[:5]

        # Symbols with no incoming or outgoing edges
        connected = {e.caller for e in self.edges} | {e.callee for e in self.edges}
        isolated = [
            sid for sid in self.symbols
            if sid not in connected and self.symbols[sid].kind == "function"
        ]

        lines = [
            f"Functions: {len(functions)}",
            f"Classes: {len(classes)}",
            f"Files: {len(files)}",
            f"Call edges: {len(self.edges)}",
        ]

        if top:
            lines.append("")
            lines.append("Most called:")
            for sid, count in top:
                sym = self.symbols.get(sid)
                name = sym.name if sym else sid
                lines.append(f"  {name} ({count} calls)")

        if isolated:
            lines.append("")
            lines.append(f"Isolated functions ({len(isolated)}):")
            for sid in isolated[:5]:
                sym = self.symbols.get(sid)
                name = sym.name if sym else sid
                lines.append(f"  {name}")
            if len(isolated) > 5:
                lines.append(f"  ... and {len(isolated) - 5} more")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Import resolution for cross-file calls
# ---------------------------------------------------------------------------

# Python: from x import y  /  import x
_PY_FROM_IMPORT_RE = re.compile(
    r"^from\s+(\.{0,3}\w[\w.]*|\.{1,3})\s+import\s+(.+)$", re.MULTILINE,
)
_PY_IMPORT_RE = re.compile(
    r"^import\s+([\w.]+)", re.MULTILINE,
)

# TS/JS: import { x } from './y'  /  import x from './y'
_TS_IMPORT_RE = re.compile(
    r"""import\s+(?:\{([^}]+)\}|(\w+))\s+from\s+['"]([^'"]+)['"]""",
)

# Go: import "pkg/path"  — Go calls are typically pkg.Func()
_GO_IMPORT_RE = re.compile(
    r"""^\s*"([^"]+)"$""", re.MULTILINE,
)


def _build_import_map_python(
    content: str, file_path: str, available_files: set[str],
) -> dict[str, str]:
    """Build name → source_file map from Python imports.

    Returns mapping of imported name to the file it comes from.
    """
    name_to_file: dict[str, str] = {}

    for m in _PY_FROM_IMPORT_RE.finditer(content):
        source = m.group(1)
        imports_raw = m.group(2).replace("(", "").replace(")", "")
        names = [
            n.strip().split(" as ")[0].strip()
            for n in imports_raw.split(",") if n.strip() and n.strip() != "*"
        ]

        # Resolve source to file
        resolved = _resolve_python_source(source, file_path, available_files)
        if resolved:
            for name in names:
                name_to_file[name] = resolved

    return name_to_file


def _resolve_python_source(
    source: str, importer: str, available_files: set[str],
) -> str | None:
    """Resolve a Python import source to a file path."""
    if source.startswith("."):
        # Relative import
        dots = len(source) - len(source.lstrip("."))
        module = source.lstrip(".")
        importer_dir = str(Path(importer).parent)

        for _ in range(dots - 1):
            importer_dir = str(Path(importer_dir).parent)

        if module:
            candidate = str(Path(importer_dir) / module.replace(".", "/")) + ".py"
            if candidate in available_files:
                return candidate
            # Try as package
            candidate = str(Path(importer_dir) / module.replace(".", "/") / "__init__.py")
            if candidate in available_files:
                return candidate
    else:
        # Absolute import
        candidate = source.replace(".", "/") + ".py"
        if candidate in available_files:
            return candidate
        candidate = source.replace(".", "/") + "/__init__.py"
        if candidate in available_files:
            return candidate

    return None


def _build_import_map_ts(
    content: str, file_path: str, available_files: set[str],
) -> dict[str, str]:
    """Build name → source_file map from TS/JS imports."""
    name_to_file: dict[str, str] = {}

    for m in _TS_IMPORT_RE.finditer(content):
        named = m.group(1)  # { x, y }
        default = m.group(2)  # default import
        source = m.group(3)  # './path'

        if not source.startswith("."):
            continue  # skip external modules

        names: list[str] = []
        if named:
            names = [n.strip().split(" as ")[0].strip() for n in named.split(",") if n.strip()]
        if default:
            names.append(default)

        resolved = _resolve_ts_source(source, file_path, available_files)
        if resolved:
            for name in names:
                name_to_file[name] = resolved

    return name_to_file


def _resolve_ts_source(
    source: str, importer: str, available_files: set[str],
) -> str | None:
    """Resolve a TS/JS import path to a file."""
    importer_dir = str(Path(importer).parent)
    base = str(Path(importer_dir) / source)

    for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
        candidate = base + ext
        if candidate in available_files:
            return candidate
    # index file
    for ext in (".ts", ".tsx", ".js", ".jsx"):
        candidate = str(Path(base) / f"index{ext}")
        if candidate in available_files:
            return candidate

    return None


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def _extract_calls_in_body(
    content: str, symbol: Symbol,
) -> list[str]:
    """Extract function call names from a symbol's body text."""
    lines = content.split("\n")
    # Get body lines (1-based to 0-based)
    start = max(0, symbol.line - 1)
    end = min(len(lines), symbol.end_line)
    body = "\n".join(lines[start:end])

    calls: list[str] = []
    seen: set[str] = set()
    for m in _CALL_RE.finditer(body):
        name = m.group(1)
        if (
            name not in SKIP_NAMES
            and name != symbol.name  # skip recursion
            and name not in seen
            and not name.startswith("_")  # skip private
        ):
            seen.add(name)
            calls.append(name)

    return calls


def build_symbol_graph(
    root_dir: str,
    files: list[str] | None = None,
) -> SymbolGraph:
    """Build a SymbolGraph from source files.

    Extracts symbols from each file, detects calls within function bodies,
    and resolves them to known symbols (same file or imported).

    Args:
        root_dir: Absolute path to the project root.
        files: Optional list of relative file paths. If None, discovers
            files using ripgrep.

    Returns:
        SymbolGraph with symbols and call edges.
    """
    root = Path(root_dir).resolve()

    # Discover files if not provided
    if files is None:
        try:
            from ..ripgrep import list_files
            discovered = list_files(root)
            files = []
            for f in discovered:
                try:
                    files.append(str(f.relative_to(root)))
                except ValueError:
                    pass
        except (ImportError, OSError, RuntimeError):
            # ImportError: ripgrep module; OSError: rg binary or file access; RuntimeError: rg failures
            files = []

    graph = SymbolGraph()
    available_files = set(files)

    # Phase 1: Extract symbols from all files + read content
    file_contents: dict[str, str] = {}
    file_symbols: dict[str, list[Symbol]] = {}

    for file_path in files:
        lang = detect_language(file_path)
        if not lang:
            continue

        abs_path = root / file_path
        try:
            content = abs_path.read_text(errors="replace")
        except OSError:
            continue

        symbols = extract_symbols(content, lang, file_path)
        if not symbols:
            continue

        file_contents[file_path] = content
        file_symbols[file_path] = symbols

        for sym in symbols:
            graph.add_symbol(sym)

    # Build SymbolIndex for fast resolution
    all_symbols = [sym for syms in file_symbols.values() for sym in syms]
    symbol_index = SymbolIndex.from_symbols(all_symbols)

    # Phase 2: Build import maps for cross-file resolution
    file_import_maps: dict[str, dict[str, str]] = {}
    for file_path, content in file_contents.items():
        lang = detect_language(file_path)
        if lang == "python":
            file_import_maps[file_path] = _build_import_map_python(
                content, file_path, available_files,
            )
        elif lang in ("typescript", "javascript"):
            file_import_maps[file_path] = _build_import_map_ts(
                content, file_path, available_files,
            )
        else:
            file_import_maps[file_path] = {}

    # Phase 3: Detect calls and resolve to symbols
    for file_path, symbols in file_symbols.items():
        content = file_contents[file_path]
        import_map = file_import_maps.get(file_path, {})

        for sym in symbols:
            if sym.kind != "function":
                continue

            calls = _extract_calls_in_body(content, sym)
            for call_name in calls:
                result = _resolve_call(
                    call_name, file_path, import_map, symbol_index,
                )
                if result:
                    callee_id, confidence = result
                    graph.add_edge(
                        CallEdge(
                            caller=sym.id,
                            callee=callee_id,
                            confidence=confidence,
                        ),
                    )

    # Phase 4 (optional): SymbolLinker bridge for cross-file type resolution
    _apply_symbol_linker(graph, file_contents)

    return graph


def _apply_symbol_linker(
    graph: SymbolGraph,
    file_contents: dict[str, str],
) -> None:
    """Optionally enhance edges with SymbolLinker cross-file type resolution.

    If the ``intelligence`` module is available, runs SymbolLinker to resolve
    additional cross-file relationships and marks them ``confidence="linked"``.
    This is a best-effort enhancement — if the module is missing the graph
    is returned unmodified.
    """
    try:
        from ..intelligence.ast_extractor import ASTSymbol
        from ..intelligence.symbol_linker import SymbolLinker
    except (ImportError, ModuleNotFoundError):
        return

    # Convert file_contents into ASTSymbol dicts for the linker.
    # We only create minimal ASTSymbol objects from graph symbols to allow
    # SymbolLinker.resolve_type() to work for cross-file type matching.
    ast_symbols: dict[str, list[ASTSymbol]] = {}
    for sym in graph.symbols.values():
        ast_sym = ASTSymbol(
            name=sym.name,
            kind=sym.kind,
            signature=f"{sym.kind} {sym.name}",
            line=sym.line,
            file=sym.file,
        )
        ast_symbols.setdefault(sym.file, []).append(ast_sym)

    try:
        linker = SymbolLinker(ast_symbols)
    except Exception:  # noqa: BLE001
        logger.debug("SymbolLinker init failed, skipping linked resolution")
        return

    # For each symbol that appears in calls but was resolved as "heuristic",
    # try to validate via SymbolLinker type resolution.
    for edge in list(graph.edges):
        if edge.confidence != "heuristic":
            continue
        callee_sym = graph.symbols.get(edge.callee)
        if callee_sym is None:
            continue
        resolved = linker.resolve_type(callee_sym.name)
        if resolved is not None and resolved.file == callee_sym.file:
            # SymbolLinker confirms this resolution — upgrade confidence
            idx = graph.edges.index(edge)
            graph.edges[idx] = CallEdge(
                caller=edge.caller,
                callee=edge.callee,
                confidence="linked",
            )


def _resolve_call(
    call_name: str,
    caller_file: str,
    import_map: dict[str, str],
    index: SymbolIndex,
) -> tuple[str, str] | None:
    """Resolve a function call name to a ``(symbol_id, confidence)`` tuple.

    Uses :class:`SymbolIndex.resolve` which implements the strategy ordering:

    1. Same-file → confidence ``"direct"``
    2. Imported  → confidence ``"imported"``
    3. Unique-global → confidence ``"heuristic"``

    Args:
        call_name: The bare function/class name being called.
        caller_file: Relative path of the file containing the call.
        import_map: Mapping of imported name → source file for *caller_file*.
        index: Pre-built :class:`SymbolIndex` over all project symbols.

    Returns:
        ``(symbol_id, confidence_str)`` on success, or ``None`` if unresolved.
    """
    # SymbolIndex.resolve handles the three strategies in order.
    resolved = index.resolve(call_name, from_file=caller_file, imports=import_map)
    if resolved is None:
        return None

    # Determine which strategy matched so we can tag confidence.
    if resolved.file == caller_file:
        return (resolved.id, "direct")

    if call_name in import_map and import_map[call_name] == resolved.file:
        return (resolved.id, "imported")

    # Unique-global fallback
    return (resolved.id, "heuristic")
