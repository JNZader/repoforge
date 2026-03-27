"""
doc_chunks.py - Pre-digested context chunks for focused documentation generation.

Instead of passing the entire project context to each chapter's LLM call,
these functions produce small, targeted summaries (~20-50 lines) that give
the LLM exactly the data it needs to format one documentation section.

Each chunk function:
  - Filters facts and AST symbols by relevance
  - Formats as a compact, human-readable list
  - Caps output to a fixed line budget
  - Returns empty string when no relevant data exists

Usage:
    from repoforge.intelligence.doc_chunks import chunk_endpoints, chunk_data_models
    endpoints_ctx = chunk_endpoints(facts, ast_symbols)
    models_ctx = chunk_data_models(facts, ast_symbols)
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..facts import FactItem
from .ast_extractor import ASTSymbol

logger = logging.getLogger(__name__)


def chunk_endpoints(
    facts: list[FactItem],
    ast_symbols: dict[str, list[ASTSymbol]],
    max_lines: int = 50,
) -> str:
    """Pre-digest endpoint data for API reference documentation.

    Takes endpoint-related facts and handler function signatures from AST,
    producing a compact list like:
        GET /health -> returns {status, version} (server.go:42)
        POST /api/observations -> handler: HandleCreateObservation(w, r) (handlers.go:88)

    Args:
        facts: All extracted facts from the project.
        ast_symbols: Dict mapping file paths to their AST symbols.
        max_lines: Maximum output lines.

    Returns:
        Formatted endpoint context string, or empty string.
    """
    lines: list[str] = []

    # 1. Collect endpoint facts
    endpoint_facts = [f for f in facts if f.fact_type == "endpoint"]
    port_facts = [f for f in facts if f.fact_type == "port"]

    if not endpoint_facts and not _has_handler_symbols(ast_symbols):
        return ""

    lines.append("## Endpoints (extracted from source code)\n")

    # Add port info if available
    if port_facts:
        ports = ", ".join(f"{f.value} ({f.file}:{f.line})" for f in port_facts[:3])
        lines.append(f"**Server port**: {ports}\n")

    # 2. Format endpoint facts with handler signatures
    handler_index = _build_handler_index(ast_symbols)

    for fact in endpoint_facts:
        if len(lines) >= max_lines:
            lines.append(f"... and {len(endpoint_facts) - len(lines) + 3} more endpoints")
            break

        line = f"- `{fact.value}` ({fact.file}:{fact.line})"

        # Try to find the handler function near this endpoint
        handler = _find_handler_near(fact.file, fact.line, handler_index)
        if handler:
            line += f" -> handler: `{handler.signature}`"

        lines.append(line)

    # 3. Add handler functions not yet associated with endpoints
    if len(lines) < max_lines:
        unmatched = _get_unmatched_handlers(handler_index, endpoint_facts)
        if unmatched:
            lines.append("\n**Handler functions** (no endpoint pattern matched):")
            for sym in unmatched[:max_lines - len(lines)]:
                lines.append(f"- `{sym.signature}` ({sym.file}:{sym.line})")

    return "\n".join(lines)


def chunk_data_models(
    facts: list[FactItem],
    ast_symbols: dict[str, list[ASTSymbol]],
    max_lines: int = 30,
) -> str:
    """Pre-digest data model information for the data models chapter.

    Formats as:
        Table: sessions | Fields: id (int64), project (string) | (store.go:120)
        Struct: Observation | Fields: ID int64, Content string | (types.go:15)

    Args:
        facts: All extracted facts from the project.
        ast_symbols: Dict mapping file paths to their AST symbols.
        max_lines: Maximum output lines.

    Returns:
        Formatted data model context string, or empty string.
    """
    lines: list[str] = []

    # 1. Database table facts
    db_facts = [f for f in facts if f.fact_type == "db_table"]

    # 2. Struct/class/interface symbols that look like data models
    model_symbols = _collect_model_symbols(ast_symbols)

    if not db_facts and not model_symbols:
        return ""

    lines.append("## Data Models (extracted from source code)\n")

    # Database tables
    if db_facts:
        lines.append("### Database Tables")
        for fact in db_facts:
            if len(lines) >= max_lines:
                break
            lines.append(f"- Table: `{fact.value}` ({fact.file}:{fact.line})")

    # Struct/class/type definitions
    if model_symbols and len(lines) < max_lines:
        lines.append("\n### Type Definitions")
        for sym in model_symbols:
            if len(lines) >= max_lines:
                break
            line = f"- `{sym.signature}`"
            if sym.fields:
                preview = "; ".join(sym.fields[:6])
                if len(sym.fields) > 6:
                    preview += "; ..."
                line += f" {{ {preview} }}"
            line += f" ({sym.file}:{sym.line})"
            lines.append(line)

    return "\n".join(lines)


def chunk_mcp_tools(
    ast_symbols: dict[str, list[ASTSymbol]],
    facts: list[FactItem],
    max_lines: int = 30,
) -> str:
    """Pre-digest MCP tool information for documentation.

    Formats as:
        Tool: mem_save | Params: title, content, type, project | Description: "Save observation"

    Args:
        ast_symbols: Dict mapping file paths to their AST symbols.
        facts: All extracted facts (used for supplementary info).
        max_lines: Maximum output lines.

    Returns:
        Formatted MCP tools context string, or empty string.
    """
    import re

    lines: list[str] = []
    tools_found: list[dict] = []

    # Look for MCP-related files and symbols
    for file_path, symbols in ast_symbols.items():
        file_lower = file_path.lower()
        is_mcp_file = any(hint in file_lower for hint in ("mcp", "tool", "server"))

        if not is_mcp_file:
            continue

        for sym in symbols:
            name_lower = sym.name.lower()
            # Look for tool registration patterns
            if any(hint in name_lower for hint in ("tool", "handle", "register")):
                tools_found.append({
                    "name": sym.name,
                    "signature": sym.signature,
                    "params": sym.params,
                    "doc": sym.docstring,
                    "file": sym.file or file_path,
                    "line": sym.line,
                })

    if not tools_found:
        return ""

    lines.append("## MCP Tools (extracted from source code)\n")

    for tool in tools_found:
        if len(lines) >= max_lines:
            break
        params = ", ".join(tool["params"][:6]) if tool["params"] else "none"
        line = f"- `{tool['name']}` | Params: {params}"
        if tool["doc"]:
            line += f' | "{tool["doc"][:60]}"'
        line += f" ({tool['file']}:{tool['line']})"
        lines.append(line)

    return "\n".join(lines)


def chunk_cli_commands(
    facts: list[FactItem],
    ast_symbols: dict[str, list[ASTSymbol]],
    max_lines: int = 20,
) -> str:
    """Pre-digest CLI command information for documentation.

    Formats as:
        Command: serve | Flags: --port, --data-dir | Description: "Start HTTP server"

    Args:
        facts: All extracted facts from the project.
        ast_symbols: Dict mapping file paths to their AST symbols.
        max_lines: Maximum output lines.

    Returns:
        Formatted CLI commands context string, or empty string.
    """
    lines: list[str] = []

    cli_facts = [f for f in facts if f.fact_type == "cli_command"]
    env_facts = [f for f in facts if f.fact_type == "env_var"]

    if not cli_facts:
        return ""

    lines.append("## CLI Commands (extracted from source code)\n")

    for fact in cli_facts:
        if len(lines) >= max_lines:
            break
        lines.append(f"- Command: `{fact.value}` ({fact.file}:{fact.line})")

    # Add env vars that CLI might use
    if env_facts and len(lines) < max_lines:
        lines.append("\n### Environment Variables")
        for fact in env_facts[:max_lines - len(lines)]:
            lines.append(f"- `{fact.value}` ({fact.file}:{fact.line})")

    return "\n".join(lines)


def chunk_architecture(
    graph_context: str,
    build_info: dict | None = None,
    max_lines: int = 30,
) -> str:
    """Pre-digest architecture information.

    Just the dependency graph + layers + top modules.

    Args:
        graph_context: Full graph context string (from graph_context.py).
        build_info: Optional build info dict from scanner.
        max_lines: Maximum output lines.

    Returns:
        Formatted architecture context string, or empty string.
    """
    if not graph_context and not build_info:
        return ""

    lines: list[str] = []

    if graph_context:
        # Take only the first max_lines lines of graph context
        graph_lines = graph_context.strip().split("\n")
        lines.extend(graph_lines[:max_lines])

    if build_info and len(lines) < max_lines:
        remaining = max_lines - len(lines)
        lines.append("\n### Build Information")
        if build_info.get("build_tool"):
            lines.append(f"- Build tool: {build_info['build_tool']}")
        if build_info.get("packages"):
            pkg_list = ", ".join(str(p) for p in list(build_info["packages"])[:5])
            lines.append(f"- Packages: {pkg_list}")

    return "\n".join(lines[:max_lines])


def chunk_module_summary(
    file_path: str,
    ast_symbols: list[ASTSymbol],
    max_lines: int = 20,
) -> str:
    """Summarize a single module's public API.

    Lists function signatures, types, and key exports.

    Args:
        file_path: Relative path to the module.
        ast_symbols: AST symbols extracted from this module.
        max_lines: Maximum output lines.

    Returns:
        Formatted module summary string, or empty string.
    """
    if not ast_symbols:
        return ""

    lines = [f"### {file_path}"]

    # Group by kind
    functions = [s for s in ast_symbols if s.kind in ("function", "method")]
    types = [s for s in ast_symbols if s.kind in ("struct", "class", "interface", "type", "enum")]
    constants = [s for s in ast_symbols if s.kind in ("constant", "variable")]

    if types:
        for sym in types:
            if len(lines) >= max_lines:
                break
            line = f"- `{sym.signature}`"
            if sym.fields:
                preview = "; ".join(sym.fields[:4])
                line += f" {{ {preview} }}"
            lines.append(line)

    if functions:
        for sym in functions:
            if len(lines) >= max_lines:
                break
            lines.append(f"- `{sym.signature}`")

    if constants and len(lines) < max_lines:
        for sym in constants[:3]:
            if len(lines) >= max_lines:
                break
            lines.append(f"- `{sym.signature}`")

    return "\n".join(lines)


def build_all_ast_symbols(
    root_dir: str,
    files: list[str],
) -> dict[str, list[ASTSymbol]]:
    """Extract AST symbols for all files, returning a dict keyed by file path.

    This is the shared extraction step used by all chunk functions.
    Gracefully returns empty dict if tree-sitter is not available.

    Args:
        root_dir: Absolute path to the project root.
        files: List of relative file paths.

    Returns:
        Dict mapping relative file path to list of ASTSymbol.
    """
    try:
        from .extractor_registry import get_ast_registry
        registry = get_ast_registry()
    except Exception:
        return {}

    if registry is None:
        return {}

    root = Path(root_dir).resolve()
    result: dict[str, list[ASTSymbol]] = {}

    for rel_path in files:
        full_path = root / rel_path
        if not full_path.is_file():
            continue
        try:
            content = full_path.read_text(errors="replace")
            symbols = registry.extract_symbols(content, rel_path)
            if symbols:
                result[rel_path] = symbols
        except Exception:
            logger.debug("Failed to extract AST symbols for %s", rel_path, exc_info=True)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _has_handler_symbols(ast_symbols: dict[str, list[ASTSymbol]]) -> bool:
    """Check if any AST symbols look like HTTP handlers."""
    handler_hints = ("handler", "handle", "route", "endpoint", "controller",
                     "get", "post", "put", "delete", "patch", "serve")
    for symbols in ast_symbols.values():
        for sym in symbols:
            if sym.kind in ("function", "method"):
                name_lower = sym.name.lower()
                if any(hint in name_lower for hint in handler_hints):
                    return True
    return False


def _build_handler_index(
    ast_symbols: dict[str, list[ASTSymbol]],
) -> dict[str, list[ASTSymbol]]:
    """Build an index of handler-like functions keyed by file path."""
    handler_hints = ("handler", "handle", "route", "endpoint", "controller",
                     "serve", "get", "post", "put", "delete", "patch",
                     "create", "update", "list", "fetch")
    index: dict[str, list[ASTSymbol]] = {}
    for file_path, symbols in ast_symbols.items():
        handlers = []
        for sym in symbols:
            if sym.kind in ("function", "method"):
                name_lower = sym.name.lower()
                if any(hint in name_lower for hint in handler_hints):
                    handlers.append(sym)
        if handlers:
            index[file_path] = handlers
    return index


def _find_handler_near(
    file_path: str,
    line: int,
    handler_index: dict[str, list[ASTSymbol]],
    max_distance: int = 15,
) -> ASTSymbol | None:
    """Find the handler function closest to a given line in the same file."""
    handlers = handler_index.get(file_path, [])
    if not handlers:
        return None

    best = None
    best_dist = max_distance + 1
    for sym in handlers:
        dist = abs(sym.line - line)
        if dist < best_dist:
            best = sym
            best_dist = dist

    return best


def _get_unmatched_handlers(
    handler_index: dict[str, list[ASTSymbol]],
    endpoint_facts: list[FactItem],
) -> list[ASTSymbol]:
    """Get handler symbols not near any endpoint fact."""
    matched_files_lines = {(f.file, f.line) for f in endpoint_facts}
    unmatched = []
    for file_path, handlers in handler_index.items():
        for sym in handlers:
            # Check if any endpoint fact is near this handler
            is_matched = any(
                fl == file_path and abs(line - sym.line) <= 15
                for fl, line in matched_files_lines
            )
            if not is_matched:
                unmatched.append(sym)
    return unmatched


def _collect_model_symbols(
    ast_symbols: dict[str, list[ASTSymbol]],
) -> list[ASTSymbol]:
    """Collect struct/class/interface symbols that look like data models."""
    model_path_hints = ("model", "schema", "entity", "type", "store", "db",
                        "domain", "struct")
    model_name_hints = ("model", "schema", "entity", "record", "row", "table",
                        "request", "response", "config", "options", "params")

    models: list[ASTSymbol] = []

    for file_path, symbols in ast_symbols.items():
        file_lower = file_path.lower()
        is_model_file = any(hint in file_lower for hint in model_path_hints)

        for sym in symbols:
            if sym.kind not in ("struct", "class", "interface", "type", "schema"):
                continue

            name_lower = sym.name.lower()
            is_model_name = any(hint in name_lower for hint in model_name_hints)

            # Include if: model-like file, model-like name, or has fields
            if is_model_file or is_model_name or sym.fields:
                models.append(sym)

    return models
