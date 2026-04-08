"""
prepare.py — Convert codebase entities into searchable text representations.

Each entity type (Symbol, ModuleInfo, Node) gets a human-readable text
description suitable for embedding. The prepare_all() function collects
all entities into a flat list of (id, entity_type, text) tuples.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..graph import Node
    from ..ir.repo import ModuleInfo
    from ..symbols.extractor import Symbol


def symbol_to_text(symbol: Symbol) -> str:
    """Convert a Symbol to searchable text.

    Example output:
        "function authenticate in src/auth.py: params: token, secret"
    """
    parts = [f"{symbol.kind} {symbol.name} in {symbol.file}"]

    if symbol.params:
        params_str = ", ".join(symbol.params)
        parts.append(f"params: {params_str}")

    return ": ".join(parts)


def module_to_text(module: ModuleInfo) -> str:
    """Convert a ModuleInfo to searchable text.

    Example output:
        "module auth at src/auth.py (python): exports authenticate, login.
         imports jwt, hashlib"
    """
    parts = [f"module {module.name} at {module.path} ({module.language})"]

    details: list[str] = []
    if module.exports:
        details.append(f"exports {', '.join(module.exports)}")
    if module.imports:
        details.append(f"imports {', '.join(module.imports)}")
    if module.summary_hint:
        details.append(module.summary_hint)

    if details:
        parts.append(". ".join(details))

    return ": ".join(parts)


def node_to_text(node: Node) -> str:
    """Convert a graph Node to searchable text.

    Example output:
        "module auth (layer: backend) at src/auth.py: exports authenticate, login"
    """
    parts = []

    label = f"{node.node_type} {node.name}"
    if node.layer:
        label += f" (layer: {node.layer})"
    if node.file_path:
        label += f" at {node.file_path}"
    parts.append(label)

    if node.exports:
        parts.append(f"exports {', '.join(node.exports)}")

    return ": ".join(parts)


def prepare_all(
    symbols: list[Symbol] | None = None,
    modules: list[ModuleInfo] | None = None,
    nodes: list[Node] | None = None,
) -> list[tuple[str, str, str]]:
    """Convert all entities into a flat list of (id, entity_type, text).

    Args:
        symbols: List of Symbol instances from extractor.
        modules: List of ModuleInfo instances from IR.
        nodes: List of Node instances from graph.

    Returns:
        List of (entity_id, entity_type, searchable_text) tuples.
    """
    results: list[tuple[str, str, str]] = []

    if symbols:
        for sym in symbols:
            results.append((sym.id, "symbol", symbol_to_text(sym)))

    if modules:
        for mod in modules:
            results.append((mod.path, "module", module_to_text(mod)))

    if nodes:
        for node in nodes:
            results.append((node.id, "node", node_to_text(node)))

    return results
