"""
graph_query.py - Query interface for code knowledge graphs.

Provides programmatic query capabilities on top of CodeGraph (file-level)
and SymbolGraph (symbol-level) for external tool consumption (MCP, etc.).

Queries:
  - callers:  who calls a given function/symbol
  - callees:  what does a given function/symbol call
  - imports:  what files does a given file import

All queries return QueryResult with consistent JSON schema.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .graph import CodeGraph
from .symbols.graph import SymbolGraph

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class QueryResult:
    """Structured result from a graph query."""

    query_type: str
    """Query type: 'callers', 'callees', or 'imports'."""

    target: str
    """The queried symbol name or file path."""

    target_found: bool
    """Whether the target was found in the graph."""

    results: list[dict] = field(default_factory=list)
    """List of result dicts (schema varies by query type)."""

    count: int = 0
    """Number of results."""

    def to_json(self) -> str:
        """Serialize to JSON string."""
        data = {
            "query": {
                "type": self.query_type,
                "target": self.target,
            },
            "target_found": self.target_found,
            "results": self.results,
            "count": self.count,
        }
        return json.dumps(data, indent=2) + "\n"


# ---------------------------------------------------------------------------
# Symbol-level queries (callers / callees)
# ---------------------------------------------------------------------------


def _find_symbols_by_name(
    graph: SymbolGraph, symbol_name: str,
) -> list[str]:
    """Find all symbol IDs matching a given name."""
    return [
        sid for sid, sym in graph.symbols.items()
        if sym.name == symbol_name
    ]


def query_callers(graph: SymbolGraph, symbol_name: str) -> QueryResult:
    """Find all functions that call the named symbol.

    Matches by symbol name (not full file::name id) and aggregates
    callers across all matching symbols.

    Args:
        graph: A built SymbolGraph.
        symbol_name: Function or class name to query.

    Returns:
        QueryResult with caller information.
    """
    matching_ids = _find_symbols_by_name(graph, symbol_name)

    if not matching_ids:
        return QueryResult(
            query_type="callers",
            target=symbol_name,
            target_found=False,
            results=[],
            count=0,
        )

    seen: set[str] = set()
    results: list[dict] = []

    for symbol_id in matching_ids:
        caller_ids = graph.get_callers(symbol_id)
        for cid in caller_ids:
            if cid in seen:
                continue
            seen.add(cid)
            sym = graph.symbols.get(cid)
            if sym:
                results.append({
                    "name": sym.name,
                    "file": sym.file,
                    "line": sym.line,
                    "kind": sym.kind,
                    "id": sym.id,
                })

    return QueryResult(
        query_type="callers",
        target=symbol_name,
        target_found=True,
        results=results,
        count=len(results),
    )


def query_callees(graph: SymbolGraph, symbol_name: str) -> QueryResult:
    """Find all functions called by the named symbol.

    Matches by symbol name and aggregates callees across all matching symbols.

    Args:
        graph: A built SymbolGraph.
        symbol_name: Function or class name to query.

    Returns:
        QueryResult with callee information.
    """
    matching_ids = _find_symbols_by_name(graph, symbol_name)

    if not matching_ids:
        return QueryResult(
            query_type="callees",
            target=symbol_name,
            target_found=False,
            results=[],
            count=0,
        )

    seen: set[str] = set()
    results: list[dict] = []

    for symbol_id in matching_ids:
        callee_ids = graph.get_callees(symbol_id)
        for cid in callee_ids:
            if cid in seen:
                continue
            seen.add(cid)
            sym = graph.symbols.get(cid)
            if sym:
                results.append({
                    "name": sym.name,
                    "file": sym.file,
                    "line": sym.line,
                    "kind": sym.kind,
                    "id": sym.id,
                })

    return QueryResult(
        query_type="callees",
        target=symbol_name,
        target_found=True,
        results=results,
        count=len(results),
    )


# ---------------------------------------------------------------------------
# File-level queries (imports)
# ---------------------------------------------------------------------------


def query_imports(graph: CodeGraph, file_path: str) -> QueryResult:
    """Find all files imported by the given file.

    Uses CodeGraph dependency edges to resolve imports.

    Args:
        graph: A built CodeGraph (v2 recommended).
        file_path: Relative file path to query.

    Returns:
        QueryResult with imported file information.
    """
    node = graph.get_node(file_path)

    if not node:
        return QueryResult(
            query_type="imports",
            target=file_path,
            target_found=False,
            results=[],
            count=0,
        )

    dep_ids = graph.get_dependencies(file_path)
    results: list[dict] = []

    for dep_id in dep_ids:
        dep_node = graph.get_node(dep_id)
        if dep_node:
            results.append({
                "file": dep_node.file_path,
                "name": dep_node.name,
                "id": dep_node.id,
            })
        else:
            results.append({
                "file": dep_id,
                "name": dep_id,
                "id": dep_id,
            })

    return QueryResult(
        query_type="imports",
        target=file_path,
        target_found=True,
        results=results,
        count=len(results),
    )
