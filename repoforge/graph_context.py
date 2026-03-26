"""
graph_context.py - Build concise dependency context from graph v2 for LLM prompts.

Provides architectural context (dependency analysis, layer detection, blast radius)
that generators inject into prompts so the LLM understands module relationships.

Also provides CodeSnippet selection: picks the most relevant source fragments
(entry points first, then most-connected) within a token budget.

Token budget: ~500 tokens for full context, ~200 for short summary.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from .graph import CodeGraph, build_graph_v2, get_blast_radius_v2, is_test_file

logger = logging.getLogger(__name__)


def build_graph_context(root_dir: str, files: list[str] | None = None) -> str:
    """Build a concise markdown summary of the dependency graph for LLM prompts.

    Args:
        root_dir: Absolute path to the project root.
        files: Optional list of relative file paths. If None, auto-discovers.

    Returns:
        Markdown string with dependency analysis (~500 tokens max).
        Returns empty string if graph building fails.
    """
    try:
        graph = build_graph_v2(root_dir, files)
    except Exception:
        logger.debug("Failed to build graph v2 for %s", root_dir, exc_info=True)
        return ""

    return format_graph_context(graph)


def build_graph_context_from_graph(graph: CodeGraph) -> str:
    """Build context from an already-built graph (avoids rebuilding).

    Same output as build_graph_context but accepts a pre-built CodeGraph.
    """
    return format_graph_context(graph)


def format_graph_context(graph: CodeGraph) -> str:
    """Format a CodeGraph into a concise markdown summary for LLM prompts.

    Returns empty string for empty graphs.
    """
    module_nodes = [n for n in graph.nodes if n.node_type == "module"]
    import_edges = [e for e in graph.edges if e.edge_type in ("imports", "depends_on")]

    if not module_nodes:
        return ""

    # Count connections per node
    connections: dict[str, int] = {}
    for n in module_nodes:
        connections[n.id] = 0
    for e in import_edges:
        connections[e.source] = connections.get(e.source, 0) + 1
        connections[e.target] = connections.get(e.target, 0) + 1

    # Isolated (no connections)
    isolated = [nid for nid, count in connections.items() if count == 0]

    # Most connected (top 5)
    sorted_nodes = sorted(connections.items(), key=lambda x: x[1], reverse=True)
    top5 = [(nid, count) for nid, count in sorted_nodes[:5] if count > 0]

    lines = [
        "## Dependency Analysis\n",
        f"**Modules**: {len(module_nodes)} | "
        f"**Dependencies**: {len(import_edges)} | "
        f"**Isolated**: {len(isolated)}\n",
    ]

    # Top connected modules with their dependents
    if top5:
        lines.append("### Most Connected Modules\n")
        for nid, count in top5:
            dependents = graph.get_dependents(nid)
            dep_names = [Path(d).stem for d in dependents[:5]]
            deps = graph.get_dependencies(nid)
            dep_of_names = [Path(d).stem for d in deps[:5]]

            parts = [f"- **{Path(nid).name}** ({count} connections)"]
            if dep_names:
                parts.append(f"  imported by: {', '.join(dep_names)}")
            if dep_of_names:
                parts.append(f"  imports: {', '.join(dep_of_names)}")
            lines.append("  ".join(parts) + "\n")

    # Layer detection — infer from directory structure
    layers = _detect_layers(module_nodes)
    if layers:
        lines.append("### Layer Detection\n")
        for layer_name, layer_files in layers.items():
            sample = ", ".join(Path(f).name for f in layer_files[:3])
            suffix = f" +{len(layer_files) - 3} more" if len(layer_files) > 3 else ""
            lines.append(f"- **{layer_name}**: {sample}{suffix}\n")

    # Simplified mermaid (top edges only — max 15)
    top_edges = _get_top_edges(graph, max_edges=15)
    if top_edges:
        lines.append("### Architecture Flow\n")
        lines.append("```mermaid\ngraph LR\n")
        for src, tgt in top_edges:
            src_name = Path(src).stem
            tgt_name = Path(tgt).stem
            lines.append(f"    {_safe_id(src_name)} --> {_safe_id(tgt_name)}\n")
        lines.append("```\n")

    return "".join(lines)


def build_short_graph_context(graph: CodeGraph) -> str:
    """Build a shorter summary (~200 tokens) for non-architecture chapters.

    Just module count, top connections, and layer list.
    """
    module_nodes = [n for n in graph.nodes if n.node_type == "module"]
    import_edges = [e for e in graph.edges if e.edge_type in ("imports", "depends_on")]

    if not module_nodes:
        return ""

    connections: dict[str, int] = {}
    for n in module_nodes:
        connections[n.id] = 0
    for e in import_edges:
        connections[e.source] = connections.get(e.source, 0) + 1
        connections[e.target] = connections.get(e.target, 0) + 1

    sorted_nodes = sorted(connections.items(), key=lambda x: x[1], reverse=True)
    top3 = [(nid, count) for nid, count in sorted_nodes[:3] if count > 0]

    lines = [
        "## Dependency Summary\n",
        f"**Modules**: {len(module_nodes)} | "
        f"**Dependencies**: {len(import_edges)}\n",
    ]

    if top3:
        lines.append("Most connected: ")
        parts = [f"{Path(nid).name} ({count})" for nid, count in top3]
        lines.append(", ".join(parts) + "\n")

    return "".join(lines)


def build_module_graph_context(graph: CodeGraph, module_path: str) -> str:
    """Build graph context specific to a single module (for skills generation).

    Includes: what this module depends on, what depends on it, blast radius.

    Args:
        graph: Pre-built CodeGraph.
        module_path: Relative file path of the module.

    Returns:
        Markdown string with module-specific dependency info.
    """
    node = graph.get_node(module_path)
    if not node:
        return ""

    deps = graph.get_dependencies(module_path)
    dependents = graph.get_dependents(module_path)
    blast = get_blast_radius_v2(graph, module_path, max_depth=2, max_files=20)

    # Detect layer from path
    layer = _infer_layer(module_path)

    lines = [
        "## Module Dependencies\n",
    ]

    if layer:
        lines.append(f"**Layer**: {layer}\n")

    if deps:
        dep_names = [Path(d).name for d in deps]
        lines.append(f"**Depends on** ({len(deps)}): {', '.join(dep_names)}\n")
    else:
        lines.append("**Depends on**: none (leaf module)\n")

    if dependents:
        dep_names = [Path(d).name for d in dependents]
        lines.append(f"**Imported by** ({len(dependents)}): {', '.join(dep_names)}\n")
    else:
        lines.append("**Imported by**: none\n")

    # Blast radius
    blast_total = len(blast.files) + len(blast.test_files)
    if blast_total > 0:
        lines.append(
            f"**Blast radius**: {blast_total} files affected "
            f"({len(blast.files)} source, {len(blast.test_files)} test)\n"
        )
    else:
        lines.append("**Blast radius**: isolated — changes here affect no other modules\n")

    return "".join(lines)


# ---------------------------------------------------------------------------
# Code snippet selection
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CodeSnippet:
    """A source code fragment selected for LLM context injection."""
    file: str           # relative file path
    content: str        # the source text
    token_estimate: int # rough token count (~4 chars per token)
    reason: str         # why it was selected ("entry_point", "most_connected", etc.)


def select_code_snippets(
    graph: CodeGraph,
    root_dir: str,
    entry_points: list[str] | None = None,
    token_budget: int = 2000,
) -> list[CodeSnippet]:
    """Select the most relevant source file snippets within a token budget.

    Selection priority:
      1. Entry point files (always included first)
      2. Most-connected modules by graph degree (imports + dependents)

    Each file is read in full and its token cost estimated at ~4 chars/token.
    Files exceeding the remaining budget are skipped.

    Args:
        graph: Pre-built CodeGraph.
        root_dir: Absolute path to the project root.
        entry_points: List of relative file paths considered entry points.
            If None, auto-detects from common patterns (main.go, main.py, etc.).
        token_budget: Maximum total estimated tokens for all snippets.

    Returns:
        List of CodeSnippet ordered by selection priority.
    """
    root = Path(root_dir).resolve()
    entry_set = set(entry_points or [])

    # Auto-detect entry points if none provided
    if not entry_set:
        entry_set = _detect_entry_points(graph)

    # Compute connection counts for ranking
    module_nodes = [n for n in graph.nodes if n.node_type == "module"]
    connections: dict[str, int] = {}
    for n in module_nodes:
        connections[n.id] = 0
    for e in graph.edges:
        if e.edge_type in ("imports", "depends_on"):
            connections[e.source] = connections.get(e.source, 0) + 1
            connections[e.target] = connections.get(e.target, 0) + 1

    # Split into entry points and others, sort others by connections desc
    entry_files = [n.id for n in module_nodes if n.id in entry_set]
    other_files = sorted(
        [n.id for n in module_nodes if n.id not in entry_set and not is_test_file(n.id)],
        key=lambda nid: connections.get(nid, 0),
        reverse=True,
    )

    snippets: list[CodeSnippet] = []
    remaining = token_budget

    for file_id, reason in (
        *((f, "entry_point") for f in entry_files),
        *((f, "most_connected") for f in other_files),
    ):
        if remaining <= 0:
            break

        content = _read_file_content(root, file_id)
        if not content:
            continue

        tokens = _estimate_tokens(content)
        if tokens > remaining:
            continue

        snippets.append(CodeSnippet(
            file=file_id,
            content=content,
            token_estimate=tokens,
            reason=reason,
        ))
        remaining -= tokens

    return snippets


def _detect_entry_points(graph: CodeGraph) -> set[str]:
    """Auto-detect entry point files from common naming patterns."""
    entry_patterns = {
        "main.go", "main.py", "app.py", "server.py", "index.ts", "index.js",
        "main.rs", "Main.java", "main.ts", "main.js", "cli.py", "cli.go",
        "manage.py", "wsgi.py", "asgi.py",
    }
    result: set[str] = set()
    for node in graph.nodes:
        if node.node_type != "module":
            continue
        name = Path(node.id).name
        if name in entry_patterns:
            result.add(node.id)
        # Also match cmd/ directories (Go convention)
        parts = Path(node.id).parts
        if len(parts) >= 2 and parts[0] == "cmd":
            result.add(node.id)
    return result


def _read_file_content(root: Path, relative_path: str) -> str:
    """Read file content, returning empty string on failure."""
    try:
        full_path = root / relative_path
        if not full_path.is_file():
            return ""
        return full_path.read_text(errors="replace")
    except OSError:
        return ""


def _estimate_tokens(content: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return max(1, len(content) // 4)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _detect_layers(nodes: list) -> dict[str, list[str]]:
    """Infer layers from directory structure of module paths."""
    layers: dict[str, list[str]] = {}

    for node in nodes:
        path = node.file_path or node.id
        if is_test_file(path):
            continue
        parts = Path(path).parts
        if len(parts) >= 2:
            # Use the top-level directory as layer name
            layer = parts[0]
            layers.setdefault(layer, []).append(path)
        else:
            layers.setdefault("root", []).append(path)

    # Filter out layers with only 1 file (noise)
    return {k: v for k, v in layers.items() if len(v) >= 1}


def _infer_layer(module_path: str) -> str:
    """Infer a layer label from directory path."""
    parts = Path(module_path).parts
    if len(parts) >= 2:
        top = parts[0].lower()
        # Common layer patterns
        layer_labels = {
            "internal": "core",
            "pkg": "core",
            "lib": "core",
            "src": "source",
            "cmd": "entrypoint",
            "api": "transport",
            "server": "transport",
            "web": "transport",
            "handlers": "transport",
            "controllers": "transport",
            "models": "data",
            "schemas": "data",
            "entities": "data",
            "services": "business",
            "domain": "business",
            "utils": "utility",
            "helpers": "utility",
            "tests": "test",
            "test": "test",
        }
        return layer_labels.get(top, top)
    return ""


def _get_top_edges(graph: CodeGraph, max_edges: int = 15) -> list[tuple[str, str]]:
    """Get the most important edges for a simplified mermaid diagram.

    Prioritizes edges between highly-connected nodes.
    """
    import_edges = [
        e for e in graph.edges
        if e.edge_type in ("imports", "depends_on")
    ]

    if not import_edges:
        return []

    # Score edges by the sum of connections of their endpoints
    connections: dict[str, int] = {}
    for e in import_edges:
        connections[e.source] = connections.get(e.source, 0) + 1
        connections[e.target] = connections.get(e.target, 0) + 1

    scored = [
        (e.source, e.target, connections.get(e.source, 0) + connections.get(e.target, 0))
        for e in import_edges
    ]
    scored.sort(key=lambda x: x[2], reverse=True)

    # Deduplicate by stem names (avoid showing multiple edges between same logical modules)
    seen = set()
    result = []
    for src, tgt, _ in scored:
        key = (Path(src).stem, Path(tgt).stem)
        if key not in seen and key[0] != key[1]:
            seen.add(key)
            result.append((src, tgt))
        if len(result) >= max_edges:
            break

    return result


def _safe_id(name: str) -> str:
    """Make a name safe for mermaid node IDs."""
    import re
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)
