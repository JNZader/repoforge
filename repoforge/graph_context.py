"""
graph_context.py - Build concise dependency context from graph v2 for LLM prompts.

Provides architectural context (dependency analysis, layer detection, blast radius)
that generators inject into prompts so the LLM understands module relationships.

Also provides CodeSnippet selection: picks the most relevant source fragments
(entry points first, then most-connected) within a token budget.

build_semantic_context() combines all context layers:
  1. Graph context (module deps, top connected)
  2. Extracted facts (endpoints, ports, env vars, etc.)
  3. Code snippets (entry points, most-connected modules)

Token budget: ~500 tokens for full context, ~200 for short summary.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from .graph import CodeGraph, build_graph_v2, get_blast_radius_v2, is_test_file
from .facts import extract_facts, FactItem
from .intelligence.ast_extractor import ASTSymbol

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

    When the intelligence engine is available, uses PageRank scores to order
    the "Most Connected Modules" section by importance rather than raw degree.

    Returns empty string for empty graphs.
    """
    module_nodes = [n for n in graph.nodes if n.node_type == "module"]
    import_edges = [e for e in graph.edges if e.edge_type in ("imports", "depends_on")]

    if not module_nodes:
        return ""

    # Count connections per node (used for isolated detection and fallback)
    connections: dict[str, int] = {}
    for n in module_nodes:
        connections[n.id] = 0
    for e in import_edges:
        connections[e.source] = connections.get(e.source, 0) + 1
        connections[e.target] = connections.get(e.target, 0) + 1

    # Isolated (no connections)
    isolated = [nid for nid, count in connections.items() if count == 0]

    # Try PageRank for ordering, fall back to degree count
    ranks = _compute_ranks(graph)

    if ranks:
        # Order by PageRank score
        sorted_nodes = sorted(
            [(nid, connections[nid]) for nid in ranks if nid in connections and connections[nid] > 0],
            key=lambda x: ranks.get(x[0], 0),
            reverse=True,
        )
        top5 = sorted_nodes[:5]
    else:
        # Fallback: order by degree
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

            rank_label = ""
            if ranks and nid in ranks:
                rank_label = f", rank {ranks[nid]:.3f}"
            parts = [f"- **{Path(nid).name}** ({count} connections{rank_label})"]
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
      2. Files ranked by PageRank score (when intelligence available),
         or by graph degree as fallback.

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

    # Try PageRank for ranking, fall back to degree count
    ranks = _compute_ranks(graph)

    module_nodes = [n for n in graph.nodes if n.node_type == "module"]

    # Split into entry points and others, sort others by rank or connections
    entry_files = [n.id for n in module_nodes if n.id in entry_set]

    if ranks:
        # Sort by PageRank score (higher = more important)
        other_files = sorted(
            [n.id for n in module_nodes if n.id not in entry_set and not is_test_file(n.id)],
            key=lambda nid: ranks.get(nid, 0),
            reverse=True,
        )
    else:
        # Fallback: sort by connection count
        connections: dict[str, int] = {}
        for n in module_nodes:
            connections[n.id] = 0
        for e in graph.edges:
            if e.edge_type in ("imports", "depends_on"):
                connections[e.source] = connections.get(e.source, 0) + 1
                connections[e.target] = connections.get(e.target, 0) + 1
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


# ---------------------------------------------------------------------------
# Semantic context — combines graph + facts + snippets
# ---------------------------------------------------------------------------

def format_api_surface(
    root_dir: str,
    files: list[str],
    max_tokens: int = 2000,
    graph: CodeGraph | None = None,
) -> str:
    """Format an API Surface section from AST-extracted symbols.

    For each file, extracts symbols via tree-sitter and formats them as
    a concise list of signatures. This gives the LLM real function names,
    parameter types, and return types so it cannot hallucinate them.

    Files are prioritised by PageRank score when a graph is available.

    Args:
        root_dir: Absolute path to the project root.
        files: List of relative file paths to extract symbols from.
        max_tokens: Token budget for the entire section (~10 tokens/signature).
        graph: Optional CodeGraph for PageRank-based ordering.

    Returns:
        Markdown string with the API Surface section, or empty string.
    """
    try:
        from .intelligence.extractor_registry import get_ast_registry
        ast_registry = get_ast_registry()
    except Exception:
        ast_registry = None

    if ast_registry is None:
        return ""

    root = Path(root_dir).resolve()

    # Determine file order: PageRank if graph available, else as-given
    if graph is not None:
        ranks = _compute_ranks(graph)
        if ranks:
            file_order = sorted(
                files,
                key=lambda f: ranks.get(f, 0),
                reverse=True,
            )
        else:
            file_order = list(files)
    else:
        file_order = list(files)

    # Extract symbols per file
    file_symbols: list[tuple[str, list[ASTSymbol]]] = []
    for rel_path in file_order:
        content = _read_file_content(root, rel_path)
        if not content:
            continue
        symbols = ast_registry.extract_symbols(content, rel_path)
        if symbols:
            file_symbols.append((rel_path, symbols))

    if not file_symbols:
        return ""

    # Also extract CLI commands and MCP tools from AST patterns
    cli_commands: list[tuple[str, str]] = []  # (command_name, file)
    mcp_tools: list[tuple[str, str]] = []  # (tool_name, file)
    for rel_path, symbols in file_symbols:
        content = _read_file_content(root, rel_path)
        if not content:
            continue
        _cmds, _tools = _extract_cli_and_mcp(content, rel_path, symbols)
        cli_commands.extend(_cmds)
        mcp_tools.extend(_tools)

    # Build the section, respecting token budget
    lines = [
        "## API Surface (from AST analysis — use these EXACT signatures)\n\n",
    ]
    token_used = _estimate_tokens(lines[0])

    for rel_path, symbols in file_symbols:
        header = f"### {rel_path}\n"
        header_tokens = _estimate_tokens(header)
        if token_used + header_tokens > max_tokens:
            break

        sig_lines: list[str] = []
        for sym in symbols:
            # Build a concise line based on symbol kind
            if sym.kind in ("struct", "interface"):
                line = f"- `{sym.signature}`"
                if sym.fields:
                    # Show first few fields inline
                    preview = "; ".join(sym.fields[:5])
                    if len(sym.fields) > 5:
                        preview += "; ..."
                    line += f" {{ {preview} }}"
            elif sym.kind in ("function", "method"):
                line = f"- `{sym.signature}`"
            elif sym.kind in ("constant", "variable"):
                line = f"- `{sym.signature}`"
            elif sym.kind == "type":
                line = f"- `{sym.signature}`"
            else:
                line = f"- `{sym.signature}`"

            if sym.docstring:
                line += f"  — {sym.docstring[:60]}"

            sig_tokens = _estimate_tokens(line + "\n")
            if token_used + header_tokens + sig_tokens > max_tokens:
                break
            sig_lines.append(line + "\n")
            token_used += sig_tokens

        if sig_lines:
            lines.append(header)
            token_used += header_tokens
            lines.extend(sig_lines)
            lines.append("\n")

    # CLI commands and MCP tools are ALWAYS included — they are high-value,
    # low-cost, and the primary reason the LLM hallucinates wrong names.
    if cli_commands:
        lines.append("### CLI Commands (from AST)\n")
        seen_cmds: set[str] = set()
        for cmd_name, cmd_file in cli_commands:
            if cmd_name not in seen_cmds:
                seen_cmds.add(cmd_name)
                lines.append(f"- `{cmd_name}` ({cmd_file})\n")
        lines.append("\n")

    if mcp_tools:
        lines.append("### MCP Tools (from AST)\n")
        seen_tools: set[str] = set()
        for tool_name, tool_file in mcp_tools:
            if tool_name not in seen_tools:
                seen_tools.add(tool_name)
                lines.append(f"- `{tool_name}` ({tool_file})\n")
        lines.append("\n")

    return "".join(lines)


def _extract_cli_and_mcp(
    content: str, file_path: str, symbols: list[ASTSymbol]
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Extract CLI commands and MCP tool registrations from source code.

    Uses regex patterns to find:
    - CLI: cobra.Command Use fields, click.command, typer commands, Go flag subcommands
    - MCP: mcp.NewTool, addTool, registerTool, server.AddTool patterns

    Returns:
        (cli_commands, mcp_tools) — each a list of (name, file_path) tuples.
    """
    import re

    cli_commands: list[tuple[str, str]] = []
    mcp_tools: list[tuple[str, str]] = []

    # --- CLI detection ---
    # Cobra: Use: "command-name"
    for m in re.finditer(r'Use:\s*"([^"]+)"', content):
        cli_commands.append((m.group(1), file_path))

    # Click: @click.command(name="...") or @app.command(name="...")
    for m in re.finditer(r'@\w+\.command\(\s*(?:name\s*=\s*)?["\']([^"\']+)["\']', content):
        cli_commands.append((m.group(1), file_path))

    # Typer: app.command(name="...")
    for m in re.finditer(r'\.command\(\s*(?:name\s*=\s*)?["\']([^"\']+)["\']', content):
        # Avoid duplicating click matches
        cmd = m.group(1)
        if (cmd, file_path) not in cli_commands:
            cli_commands.append((cmd, file_path))

    # Go subcommand registration: rootCmd.AddCommand(serveCmd) — infer from var names
    for m in re.finditer(r'AddCommand\((\w+)Cmd\)', content):
        cli_commands.append((m.group(1), file_path))

    # Go switch/case CLI dispatch: case "serve":, case "mcp":
    # Common in simple Go CLIs that use os.Args[1] switch.
    # Only match in likely CLI entry-point files to avoid noise from TUI/test code.
    _cli_path_hints = ("cmd/", "main.", "cli.", "/cli/", "entrypoint")
    if any(hint in file_path.lower() for hint in _cli_path_hints):
        # Filter: must be 2+ chars, alphabetic start, no single-char commands
        _noise = {"true", "false", "yes", "no", "on", "off", "ok", "err",
                  "default", "nil", "null", "none", "unknown", "no-args",
                  "windows", "linux", "darwin"}
        for m in re.finditer(r'case\s+"([a-z][\w-]*)"\s*:', content):
            cmd = m.group(1)
            if len(cmd) < 2 or cmd in _noise or cmd.startswith("-"):
                continue
            if (cmd, file_path) not in cli_commands:
                cli_commands.append((cmd, file_path))

    # Python argparse: subparsers.add_parser("command")
    for m in re.finditer(r'add_parser\s*\(\s*["\']([^"\']+)["\']', content):
        cmd = m.group(1)
        if (cmd, file_path) not in cli_commands:
            cli_commands.append((cmd, file_path))

    # --- MCP tool detection ---
    # mcp.NewTool("tool_name", ...) or server.AddTool(mcp.NewTool("tool_name"...
    for m in re.finditer(r'(?:NewTool|AddTool|registerTool)\s*\(\s*["\']([^"\']+)["\']', content):
        mcp_tools.append((m.group(1), file_path))

    # Python MCP: @server.tool() def tool_name or server.add_tool("name"...)
    for m in re.finditer(r'add_tool\s*\(\s*["\']([^"\']+)["\']', content):
        mcp_tools.append((m.group(1), file_path))

    # Go pattern: mcp.NewTool("tool_name") — commonly seen in engram
    # Already covered above, but also catch: Tool{Name: "tool_name"}
    for m in re.finditer(r'(?:Tool\s*\{\s*Name|ToolName|tool_name)\s*:\s*["\']([^"\']+)["\']', content):
        if (m.group(1), file_path) not in mcp_tools:
            mcp_tools.append((m.group(1), file_path))

    return cli_commands, mcp_tools


# Human-readable labels for fact types
_FACT_TYPE_LABELS: dict[str, str] = {
    "endpoint": "HTTP Endpoints",
    "port": "Port Configuration",
    "version": "Version",
    "db_table": "Database Tables",
    "cli_command": "CLI Commands",
    "env_var": "Environment Variables",
    "mcp_tool": "MCP Tools",
    "fts_ddl": "FTS Virtual Tables",
    "struct_field": "Struct Fields",
    "go_version": "Go Version",
}


def format_facts_section(facts: list[FactItem]) -> str:
    """Format a list of FactItems into a markdown section.

    Groups facts by type with human-readable headings.
    Returns empty string if no facts provided.
    """
    if not facts:
        return ""

    # Group by fact_type
    grouped: dict[str, list[FactItem]] = {}
    for f in facts:
        grouped.setdefault(f.fact_type, []).append(f)

    lines = ["## Extracted Facts\n"]

    for fact_type, items in grouped.items():
        label = _FACT_TYPE_LABELS.get(fact_type, fact_type.replace("_", " ").title())
        lines.append(f"### {label}\n")
        for item in items:
            lines.append(f"- {item.value} ({item.file}:{item.line})\n")
        lines.append("")

    return "".join(lines)


def format_snippets_section(snippets: list[CodeSnippet]) -> str:
    """Format a list of CodeSnippets into a markdown section.

    When tree-sitter is available, enriches snippets with extracted
    function/class signatures for more informative context.

    Returns empty string if no snippets provided.
    """
    if not snippets:
        return ""

    # Try to get AST registry for signature extraction
    ast_registry = None
    try:
        from .intelligence.extractor_registry import get_ast_registry
        ast_registry = get_ast_registry()
    except Exception:
        pass

    lines = ["## Key Source Code\n"]

    for snippet in snippets:
        # Detect language from extension for code fence
        ext = Path(snippet.file).suffix.lower()
        lang_map = {
            ".py": "python", ".go": "go", ".ts": "typescript", ".tsx": "typescript",
            ".js": "javascript", ".jsx": "javascript", ".rs": "rust", ".java": "java",
            ".rb": "ruby", ".cs": "csharp", ".cpp": "cpp", ".c": "c",
        }
        lang = lang_map.get(ext, "")

        reason_label = snippet.reason.replace("_", " ")
        lines.append(f"### {snippet.file} ({reason_label})\n")

        # If AST extraction available, add a signatures summary before the code
        if ast_registry is not None:
            try:
                symbols = ast_registry.extract_symbols(snippet.content, snippet.file)
                if symbols:
                    lines.append("**Signatures:**\n")
                    for sym in symbols[:15]:  # Cap at 15 to avoid bloat
                        lines.append(f"- `{sym.signature}`\n")
                    lines.append("\n")
            except Exception:
                pass  # Graceful fallback — just show the raw code

        lines.append(f"```{lang}\n{snippet.content}\n```\n\n")

    return "".join(lines)


def build_semantic_context(
    root_dir: str,
    files: list[str],
    graph: CodeGraph | None = None,
    include_snippets: bool = True,
) -> str:
    """Combine all context layers into a single markdown string for LLM prompts.

    Layers:
      1. Graph context (module deps, top connected) — from graph
      2. Extracted facts (endpoints, ports, env vars) — from extract_facts
      3. Code snippets (entry points, most-connected) — from select_code_snippets

    Each layer gracefully degrades: if one fails or returns empty, the others
    still produce output.

    Args:
        root_dir: Absolute path to the project root.
        files: List of relative file paths to extract facts from.
        graph: Pre-built CodeGraph. If None, builds one (may fail gracefully).
        include_snippets: Whether to include code snippets (set False to save tokens).

    Returns:
        Markdown string combining all available context layers.
        Returns empty string only if ALL layers produce nothing.
    """
    sections: list[str] = []

    # 1. Graph context
    _graph = graph
    if _graph is None:
        try:
            _graph = build_graph_v2(root_dir, files if files else None)
        except Exception:
            logger.debug("Failed to build graph for semantic context", exc_info=True)
            _graph = None

    if _graph is not None:
        graph_ctx = format_graph_context(_graph)
        if graph_ctx:
            sections.append(graph_ctx)

    # 2. Extracted facts
    try:
        facts = extract_facts(root_dir, files)
        facts_section = format_facts_section(facts)
        if facts_section:
            sections.append(facts_section)
    except Exception:
        logger.debug("Failed to extract facts for semantic context", exc_info=True)

    # 3. API Surface (real signatures from AST — placed BEFORE snippets)
    try:
        api_surface = format_api_surface(root_dir, files, graph=_graph)
        if api_surface:
            sections.append(api_surface)
    except Exception:
        logger.debug("Failed to build API surface for semantic context", exc_info=True)

    # 4. Code snippets (optional — can be heavy on tokens)
    if include_snippets and _graph is not None:
        try:
            snippets = select_code_snippets(_graph, root_dir)
            snippets_section = format_snippets_section(snippets)
            if snippets_section:
                sections.append(snippets_section)
        except Exception:
            logger.debug("Failed to select code snippets for semantic context", exc_info=True)

    return "\n".join(sections)


def build_module_facts_context(root_dir: str, module_path: str, files: list[str]) -> str:
    """Build facts context filtered to a specific module.

    Returns only facts from the given module file, formatted as markdown.
    Useful for per-module skill generation.
    """
    try:
        facts = extract_facts(root_dir, [module_path])
        return format_facts_section(facts)
    except Exception:
        logger.debug("Failed to extract module facts for %s", module_path, exc_info=True)
        return ""


def build_facts_only_context(
    root_dir: str,
    files: list[str],
    facts: list[FactItem],
    api_surface: str,
    compressed_sigs: dict[str, str],
    build_info: dict | None = None,
    max_tokens: int = 1500,
) -> str:
    """Build a facts-only markdown context — no graph, no raw code snippets.

    Assembles sections in order:
      1. Extracted Facts (via format_facts_section)
      2. API Surface (pre-formatted string from caller)
      3. Compressed Signatures (code blocks per file, token-budgeted)
      4. Build Info (module path, Go version, dependency count)

    Sections with empty/None data are skipped gracefully.

    Args:
        root_dir: Absolute path to the project root (unused, reserved).
        files: List of relative file paths (unused, reserved for filtering).
        facts: List of FactItem extracted from the codebase.
        api_surface: Pre-formatted API surface markdown string.
        compressed_sigs: Mapping of relative file path → compressed signature text.
        build_info: Optional dict with keys like module_path, go_version, dependencies.
        max_tokens: Token budget for the compressed signatures section.

    Returns:
        Combined markdown string with all non-empty sections.
    """
    sections: list[str] = []

    # 1. Extracted Facts
    if facts:
        facts_section = format_facts_section(facts)
        if facts_section:
            sections.append(facts_section)

    # 2. API Surface
    if api_surface:
        sections.append(api_surface)

    # 3. Compressed Signatures (token-budgeted)
    if compressed_sigs:
        sig_section = _format_compressed_sigs(compressed_sigs, max_tokens)
        if sig_section:
            sections.append(sig_section)

    # 4. Build Info
    if build_info:
        build_section = _format_build_info(build_info)
        if build_section:
            sections.append(build_section)

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Per-chapter fact filtering for facts-only mode
# ---------------------------------------------------------------------------

CHAPTER_FACT_TYPES: dict[str, set[str]] = {
    "index.md": set(),  # No facts needed for nav hub
    "01-overview.md": {"version", "go_version", "port"},
    "02-quickstart.md": {"port", "env_var", "cli_command", "go_version"},
    # 03-architecture excluded (uses full graph context)
    "04-core-mechanisms.md": {"mcp_tool", "struct_field", "env_var"},
    "05-data-models.md": {"db_table", "struct_field", "fts_ddl"},
    "06-api-reference.md": {"endpoint", "mcp_tool", "cli_command", "port"},
    "07-dev-guide.md": {"env_var", "cli_command", "go_version", "version"},
}

CHAPTER_TOKEN_BUDGETS: dict[str, int] = {
    "01-overview.md": 400,
    "02-quickstart.md": 500,
    "04-core-mechanisms.md": 600,
    "05-data-models.md": 500,
    "06-api-reference.md": 700,
    "07-dev-guide.md": 400,
}

_CHAPTER_SIG_LIMITS: dict[str, int] = {
    "01-overview.md": 3,
    "02-quickstart.md": 3,
    "06-api-reference.md": 5,
}
_DEFAULT_SIG_LIMIT = 3


def filter_facts_for_chapter(
    chapter_file: str,
    facts: list[FactItem],
) -> list[FactItem]:
    """Filter facts to only those relevant for a given chapter.

    Looks up allowed fact types from CHAPTER_FACT_TYPES.
    If the chapter is not in the mapping (adaptive/project-specific chapters),
    returns all facts as a safe fallback.

    Args:
        chapter_file: Chapter filename (e.g. "05-data-models.md").
        facts: Full list of FactItem extracted from the codebase.

    Returns:
        Filtered list of FactItem matching the chapter's allowed types,
        or the full list if the chapter is unknown.
    """
    if chapter_file not in CHAPTER_FACT_TYPES:
        return facts

    allowed = CHAPTER_FACT_TYPES[chapter_file]
    if not allowed:
        return []

    return [f for f in facts if f.fact_type in allowed]


def build_facts_only_context_for_chapter(
    chapter_file: str,
    root_dir: str,
    files: list[str],
    facts: list[FactItem],
    api_surface: str,
    compressed_sigs: dict[str, str],
    build_info: dict | None = None,
) -> str:
    """Build a facts-only context tailored for a specific chapter.

    Wraps build_facts_only_context() with per-chapter filtering:
      - Facts are filtered to types relevant for the chapter.
      - Compressed signatures are capped to a per-chapter file limit.
      - Token budget is looked up from CHAPTER_TOKEN_BUDGETS.
      - API surface is included only for chapters that need it.

    Args:
        chapter_file: Chapter filename (e.g. "06-api-reference.md").
        root_dir: Absolute path to the project root.
        files: List of relative file paths.
        facts: Full list of FactItem from the codebase.
        api_surface: Pre-formatted API surface markdown string.
        compressed_sigs: Mapping of relative file path -> compressed signature text.
        build_info: Optional build metadata dict.

    Returns:
        Combined markdown string with chapter-relevant sections.
    """
    # Filter facts to chapter-relevant types
    filtered_facts = filter_facts_for_chapter(chapter_file, facts)

    # Cap compressed sigs to per-chapter file limit
    sig_limit = _CHAPTER_SIG_LIMITS.get(chapter_file, _DEFAULT_SIG_LIMIT)
    if compressed_sigs:
        limited_sigs = dict(list(sorted(compressed_sigs.items()))[:sig_limit])
    else:
        limited_sigs = {}

    # Token budget for compressed sigs
    max_tokens = CHAPTER_TOKEN_BUDGETS.get(chapter_file, 500)

    # API surface: include for overview, data-models, api-reference; skip otherwise
    chapter_api_surface = ""
    if chapter_file in (
        "01-overview.md",
        "05-data-models.md",
        "06-api-reference.md",
    ):
        chapter_api_surface = api_surface

    return build_facts_only_context(
        root_dir=root_dir,
        files=files,
        facts=filtered_facts,
        api_surface=chapter_api_surface,
        compressed_sigs=limited_sigs,
        build_info=build_info,
        max_tokens=max_tokens,
    )


def _format_compressed_sigs(
    compressed_sigs: dict[str, str],
    max_tokens: int,
) -> str:
    """Format compressed signatures as code blocks per file within a token budget.

    Files are ordered alphabetically.  Stops adding files once the token
    budget is exhausted (tokens estimated at ~4 chars/token).
    """
    if not compressed_sigs:
        return ""

    # Language detection from extension for code fences
    lang_map = {
        ".py": "python", ".go": "go", ".ts": "typescript", ".tsx": "typescript",
        ".js": "javascript", ".jsx": "javascript", ".rs": "rust", ".java": "java",
        ".rb": "ruby", ".cs": "csharp", ".cpp": "cpp", ".c": "c",
    }

    sorted_files = sorted(compressed_sigs.keys())

    lines = ["## Compressed Signatures\n"]
    token_used = _estimate_tokens(lines[0])

    for file_path in sorted_files:
        sig_text = compressed_sigs[file_path]
        if not sig_text:
            continue

        ext = Path(file_path).suffix.lower()
        lang = lang_map.get(ext, "")

        block = f"### {file_path}\n```{lang}\n{sig_text}\n```\n"
        block_tokens = _estimate_tokens(block)

        if token_used + block_tokens > max_tokens:
            break

        lines.append(block)
        token_used += block_tokens

    # Only return if we added at least one file beyond the header
    if len(lines) <= 1:
        return ""

    return "".join(lines)


def _format_build_info(build_info: dict) -> str:
    """Format build metadata into a markdown section.

    Recognises keys: module_path, go_version, dependencies (count or list).
    Returns empty string if no recognised keys are present.
    """
    if not build_info:
        return ""

    lines = ["## Build Info\n"]
    has_content = False

    if "module_path" in build_info:
        lines.append(f"- **Module**: {build_info['module_path']}\n")
        has_content = True

    if "go_version" in build_info:
        lines.append(f"- **Go version**: {build_info['go_version']}\n")
        has_content = True

    if "dependencies" in build_info:
        deps = build_info["dependencies"]
        if isinstance(deps, (list, tuple)):
            lines.append(f"- **Dependencies**: {len(deps)}\n")
        else:
            lines.append(f"- **Dependencies**: {deps}\n")
        has_content = True

    return "".join(lines) if has_content else ""


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


def _compute_ranks(graph: CodeGraph) -> dict[str, float]:
    """Compute PageRank scores if intelligence engine is available.

    Returns empty dict if ranker is not available or fails.
    """
    try:
        from .intelligence.ranker import pagerank
        return pagerank(graph)
    except Exception:
        logger.debug("PageRank computation unavailable or failed", exc_info=True)
        return {}
