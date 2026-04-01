"""
Symbol Graph Renderer — Mermaid output for symbol-level dependency graphs.

Generates Mermaid flowchart diagrams from SymbolGraph, grouping symbols
by file and showing call relationships between functions.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from .graph import SymbolGraph


def _mermaid_id(raw: str) -> str:
    """Convert a symbol id to a valid Mermaid node identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw)


def _mermaid_safe(text: str) -> str:
    """Escape text for use in Mermaid labels."""
    return re.sub(r"[\"'\[\]{}|<>]", "", text)


def render_symbol_mermaid(
    graph: SymbolGraph,
    max_symbols: int = 60,
) -> str:
    """Render a SymbolGraph as a Mermaid flowchart.

    Groups symbols by file into subgraphs. Shows call edges between
    function nodes. Caps output at max_symbols most-connected symbols.

    Args:
        graph: The SymbolGraph to render.
        max_symbols: Maximum symbols to include (default 60).

    Returns:
        Mermaid flowchart string (without fences).
    """
    if not graph.symbols:
        return "graph LR\n    empty[No symbols detected]"

    # Rank symbols by connection count
    connections: dict[str, int] = defaultdict(int)
    for e in graph.edges:
        connections[e.caller] += 1
        connections[e.callee] += 1

    # Select top N symbols
    ranked = sorted(
        graph.symbols.values(),
        key=lambda s: connections.get(s.id, 0),
        reverse=True,
    )
    selected = ranked[:max_symbols]
    selected_ids = {s.id for s in selected}

    # Group by file
    by_file: dict[str, list] = defaultdict(list)
    for s in selected:
        by_file[s.file].append(s)

    lines = ["graph LR"]

    # Render subgraphs per file
    for file_path, symbols in sorted(by_file.items()):
        safe_file = _mermaid_id(file_path)
        display_name = _mermaid_safe(Path(file_path).name)
        lines.append(f"    subgraph {safe_file}[{display_name}]")
        for s in symbols:
            safe_id = _mermaid_id(s.id)
            shape = "([" if s.kind == "class" else "["
            end_shape = "])" if s.kind == "class" else "]"
            label = _mermaid_safe(s.name)
            lines.append(f"        {safe_id}{shape}{label}{end_shape}")
        lines.append("    end")

    # Render call edges
    for e in graph.edges:
        if e.caller in selected_ids and e.callee in selected_ids:
            src = _mermaid_id(e.caller)
            tgt = _mermaid_id(e.callee)
            lines.append(f"    {src} --> {tgt}")

    return "\n".join(lines)
