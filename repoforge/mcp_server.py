"""MCP Server for repoforge — deterministic tools + rich context resources.

Exposes repoforge's analysis capabilities as MCP tools that AI agents
(Claude Code, Claude Desktop) can call directly. No LLM calls inside —
the host agent uses its own model for generation.

Tools (deterministic, free):
  - repoforge_score: Score documentation quality
  - repoforge_graph: Build code knowledge graph + detect architecture patterns
  - repoforge_scan: Security scan generated output
  - repoforge_changelog: Generate changelog from git history
  - repoforge_drift: Check if docs are stale vs source
  - repoforge_analyze: Dead code + complexity analysis

Resources (context for the host agent):
  - repoforge://context/{path}: Full project context (facts, API surface, graph)
  - repoforge://facts/{path}: Extracted facts only
  - repoforge://api-surface/{path}: Public API surface

Usage:
  Add to ~/.claude/settings.json:
  {
    "mcpServers": {
      "repoforge": {
        "command": "uv",
        "args": ["--directory", "/path/to/repoforge", "run", "python", "-m", "repoforge.mcp_server"]
      }
    }
  }
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
)

logger = logging.getLogger(__name__)

app = Server("repoforge")


# ---------------------------------------------------------------------------
# Tools (deterministic — no LLM)
# ---------------------------------------------------------------------------


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="repoforge_score",
            description="Score documentation quality across 4 dimensions (structure, completeness, code quality, clarity). Returns per-file scores with PASS/WARN/FAIL grades. No LLM needed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "docs_dir": {"type": "string", "description": "Path to docs directory to score"},
                    "format": {"type": "string", "enum": ["table", "json"], "default": "table"},
                },
                "required": ["docs_dir"],
            },
        ),
        Tool(
            name="repoforge_graph",
            description="Build code knowledge graph from a repository. Detects architecture patterns (layered, multi-layer, hub-spoke, circular deps) and generates Mermaid diagrams.",
            inputSchema={
                "type": "object",
                "properties": {
                    "working_dir": {"type": "string", "description": "Path to repository root"},
                    "format": {"type": "string", "enum": ["summary", "mermaid", "json"], "default": "summary"},
                },
                "required": ["working_dir"],
            },
        ),
        Tool(
            name="repoforge_changelog",
            description="Generate a Keep-a-Changelog-style changelog from git history. Groups by conventional commit type. No LLM needed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "working_dir": {"type": "string", "description": "Path to repository root"},
                    "max_commits": {"type": "integer", "default": 50},
                },
                "required": ["working_dir"],
            },
        ),
        Tool(
            name="repoforge_drift",
            description="Check if generated documentation is stale relative to source code by comparing file hashes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "working_dir": {"type": "string", "description": "Path to repository root"},
                    "docs_dir": {"type": "string", "description": "Path to docs directory", "default": "docs"},
                },
                "required": ["working_dir"],
            },
        ),
        Tool(
            name="repoforge_analyze",
            description="Analyze code quality: dead code detection + cyclomatic complexity. No LLM needed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "working_dir": {"type": "string", "description": "Path to repository root"},
                },
                "required": ["working_dir"],
            },
        ),
        Tool(
            name="repoforge_context",
            description="Extract rich project context (facts, API surface, graph, architecture patterns) for documentation generation. Returns structured context that you can use to write docs yourself.",
            inputSchema={
                "type": "object",
                "properties": {
                    "working_dir": {"type": "string", "description": "Path to repository root"},
                },
                "required": ["working_dir"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "repoforge_score":
            return [TextContent(type="text", text=_tool_score(arguments))]
        elif name == "repoforge_graph":
            return [TextContent(type="text", text=_tool_graph(arguments))]
        elif name == "repoforge_changelog":
            return [TextContent(type="text", text=_tool_changelog(arguments))]
        elif name == "repoforge_drift":
            return [TextContent(type="text", text=_tool_drift(arguments))]
        elif name == "repoforge_analyze":
            return [TextContent(type="text", text=_tool_analyze(arguments))]
        elif name == "repoforge_context":
            return [TextContent(type="text", text=_tool_context(arguments))]
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except (OSError, ValueError, RuntimeError, KeyError) as e:
        # OSError: file I/O errors; ValueError: invalid arguments
        # RuntimeError: tool execution errors; KeyError: missing required args
        return [TextContent(type="text", text=f"Error: {e}")]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _tool_score(args: dict) -> str:
    from .scoring import DocScorer
    scorer = DocScorer()
    scores = scorer.score_directory(args["docs_dir"])
    fmt = args.get("format", "table")
    return scorer.report(scores, fmt=fmt)


def _tool_graph(args: dict) -> str:
    from .graph import build_graph_v2
    from .knowledge import detect_architecture_patterns, generate_architecture_mermaid

    root = args["working_dir"]
    fmt = args.get("format", "summary")
    graph = build_graph_v2(root)

    if fmt == "mermaid":
        return generate_architecture_mermaid(graph)
    elif fmt == "json":
        patterns = detect_architecture_patterns(graph)
        data = {
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
            "patterns": [
                {"name": p.name, "confidence": p.confidence, "description": p.description}
                for p in patterns
            ],
        }
        return json.dumps(data, indent=2)
    else:
        patterns = detect_architecture_patterns(graph)
        lines = [
            f"Code Graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges",
            "",
            "Architecture Patterns Detected:",
        ]
        for p in patterns:
            lines.append(f"  - {p.name} (confidence: {p.confidence}): {p.description}")
        if not patterns:
            lines.append("  (none detected)")
        lines.append("")
        lines.append("Mermaid Diagram:")
        lines.append("```mermaid")
        lines.append(generate_architecture_mermaid(graph))
        lines.append("```")
        return "\n".join(lines)


def _tool_changelog(args: dict) -> str:
    from .generators import generate_changelog
    return generate_changelog(
        Path(args["working_dir"]),
        max_commits=args.get("max_commits", 50),
    ) or "(no git history found)"


def _tool_drift(args: dict) -> str:
    from .ci import detect_doc_drift
    root = Path(args["working_dir"])
    docs_dir = root / args.get("docs_dir", "docs")
    report = detect_doc_drift(root, docs_dir=docs_dir)
    return json.dumps({
        "source_hash": report.source_hash[:12] + "...",
        "docs_hash": report.docs_hash[:12] + "..." if report.docs_hash else "(no docs)",
        "is_stale": report.is_stale,
    }, indent=2)


def _tool_analyze(args: dict) -> str:
    from .analysis import analyze_complexity, detect_dead_code
    from .intelligence.doc_chunks import build_all_ast_symbols

    root = args["working_dir"]
    from .scanner import scan_repo
    repo_map = scan_repo(root)
    all_files = [
        m["path"] for layer in repo_map["layers"].values()
        for m in layer.get("modules", [])
    ]

    # Dead code via AST symbols
    ast_symbols = build_all_ast_symbols(root, all_files)
    dead = detect_dead_code(ast_symbols)

    # Complexity via source content
    contents = {}
    for f in all_files[:50]:  # cap for performance
        p = Path(root) / f
        if p.is_file():
            try:
                contents[f] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass  # File unreadable or deleted between check and read
    complexity = analyze_complexity(contents)

    lines = [f"Analysis of {root}", ""]

    if dead.unreferenced:
        lines.append(f"Dead Code ({len(dead.unreferenced)} unreferenced functions):")
        for sym in dead.unreferenced[:15]:
            lines.append(f"  - {sym.name} ({sym.file}:{sym.line})")
        if len(dead.unreferenced) > 15:
            lines.append(f"  ... and {len(dead.unreferenced) - 15} more")
    else:
        lines.append("Dead Code: none detected")

    lines.append("")
    if complexity.modules:
        lines.append("Complexity (top 10 most complex):")
        for m in complexity.modules[:10]:
            lines.append(
                f"  - {m.file}: avg={m.avg_complexity:.1f} max={m.max_complexity:.0f}"
                f" ({m.function_count} functions, most complex: {m.most_complex})"
            )
    else:
        lines.append("Complexity: no functions analyzed")

    return "\n".join(lines)


def _tool_context(args: dict) -> str:
    """Extract rich project context for the host agent to use."""
    from .facts import extract_facts
    from .graph_context import build_short_graph_context, format_api_surface, format_facts_section
    from .knowledge import detect_architecture_patterns, generate_architecture_mermaid
    from .scanner import scan_repo

    root = args["working_dir"]
    repo_map = scan_repo(root)
    all_files = [
        m["path"] for layer in repo_map["layers"].values()
        for m in layer.get("modules", [])
    ]

    # Facts
    facts = extract_facts(root, all_files)
    facts_text = format_facts_section(facts)

    # Graph + patterns
    try:
        from .graph import build_graph_v2
        graph = build_graph_v2(root)
        short_graph = build_short_graph_context(graph)
        patterns = detect_architecture_patterns(graph)
        mermaid = generate_architecture_mermaid(graph)
    except (ImportError, OSError, ValueError, RuntimeError):
        # ImportError: graph module not available; others: graph build/analysis failures
        short_graph = ""
        patterns = []
        mermaid = ""

    # API surface
    try:
        api_surface = format_api_surface(root, all_files, graph=graph if 'graph' in dir() else None)
    except (ImportError, OSError, ValueError, RuntimeError):
        # API surface extraction failures — degrade gracefully
        api_surface = ""

    lines = [
        f"# Project Context: {repo_map.get('repoforge_config', {}).get('project_name', Path(root).name)}",
        f"Tech Stack: {', '.join(repo_map['tech_stack'])}",
        f"Files: {repo_map.get('stats', {}).get('total_files', '?')}",
        f"Layers: {', '.join(repo_map['layers'].keys())}",
        "",
    ]

    if patterns:
        lines.append("## Architecture Patterns")
        for p in patterns:
            lines.append(f"- **{p.name}** ({p.confidence}): {p.description}")
        lines.append("")

    if mermaid:
        lines.append("## Dependency Diagram")
        lines.append("```mermaid")
        lines.append(mermaid)
        lines.append("```")
        lines.append("")

    if facts_text:
        lines.append("## Extracted Facts")
        lines.append(facts_text)
        lines.append("")

    if api_surface:
        lines.append("## API Surface")
        lines.append(api_surface)
        lines.append("")

    if short_graph:
        lines.append("## Module Dependencies")
        lines.append(short_graph)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
