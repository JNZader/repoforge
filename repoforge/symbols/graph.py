"""
Symbol Graph — call-level dependency graph between functions/classes.

Builds a graph where nodes are symbols (functions, classes) and edges
represent call relationships. Supports both intra-file and cross-file
call resolution via import analysis.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import json
from collections import defaultdict

from .extractor import (
    SKIP_NAMES,
    Symbol,
    _CALL_RE,
    detect_language,
    extract_symbols,
)

logger = logging.getLogger(__name__)


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
                {"caller": e.caller, "callee": e.callee}
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
        except Exception:
            files = []

    graph = SymbolGraph()
    available_files = set(files)

    # Phase 1: Extract symbols from all files + read content
    file_contents: dict[str, str] = {}
    file_symbols: dict[str, list[Symbol]] = {}
    # name → [symbol_id] index for resolution
    name_index: dict[str, list[str]] = {}

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
            name_index.setdefault(sym.name, []).append(sym.id)

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
                resolved = _resolve_call(
                    call_name, file_path, import_map,
                    name_index, file_symbols,
                )
                if resolved:
                    graph.add_edge(CallEdge(caller=sym.id, callee=resolved))

    return graph


def _resolve_call(
    call_name: str,
    caller_file: str,
    import_map: dict[str, str],
    name_index: dict[str, list[str]],
    file_symbols: dict[str, list[Symbol]],
) -> str | None:
    """Resolve a function call name to a symbol id.

    Resolution order:
    1. Same-file symbol with matching name
    2. Imported symbol (via import_map → target file → symbol)
    3. Any symbol with matching name (first match)
    """
    # 1. Same-file match
    same_file_id = f"{caller_file}::{call_name}"
    if same_file_id in name_index.get(call_name, []):
        return same_file_id

    # 2. Import-based match
    if call_name in import_map:
        target_file = import_map[call_name]
        target_id = f"{target_file}::{call_name}"
        if call_name in name_index and target_id in name_index[call_name]:
            return target_id

    # 3. Global match (first definition wins)
    candidates = name_index.get(call_name, [])
    if candidates:
        # Prefer non-same-file to avoid false self-references
        for cid in candidates:
            if not cid.startswith(f"{caller_file}::"):
                return cid
        return candidates[0]

    return None
