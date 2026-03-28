"""Pipeline Stage 3b-3e: Build all documentation contexts.

Extracts graph context, semantic facts, API surface, doc chunks,
and facts-only per-chapter contexts from the scanned repo.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def build_all_contexts(
    root: Path,
    repo_map: dict,
    log,
    *,
    chunked: bool = False,
    facts_only: bool = False,
) -> dict:
    """Build all context strings needed by chapter prompt generation.

    Returns a dict with keys: graph_ctx, short_graph_ctx, semantic_ctx,
    facts_ctx, api_surface_ctx, doc_chunks, fo_context_by_chapter, _graph,
    _facts, _pp_build_info, _pp_ast_symbols.
    """
    all_files = [
        m["path"]
        for layer in repo_map["layers"].values()
        for m in layer.get("modules", [])
    ]

    result = {
        "graph_ctx": "",
        "short_graph_ctx": "",
        "semantic_ctx": "",
        "facts_ctx": "",
        "api_surface_ctx": "",
        "doc_chunks": {},
        "fo_context_by_chapter": None,
        "_graph": None,
        "_facts": [],
        "_all_files": all_files,
    }

    # 3b. Build dependency graph
    _build_graph(root, result, log)

    # 3b. Build semantic context
    _build_semantic(root, all_files, result, log)

    # 3c. Extract API surface
    _build_api_surface(root, all_files, result, log)

    # 3d. Build doc chunks (--chunked flag)
    if chunked:
        _build_doc_chunks(root, all_files, repo_map, result, log)
    else:
        log("📄 Full-context mode (default). Use --chunked for per-chapter chunks.")

    # 3e. Build facts-only per-chapter contexts (--facts-only flag)
    if facts_only:
        _build_facts_only(root, all_files, repo_map, result, log)

    return result


def _build_graph(root: Path, result: dict, log) -> None:
    from ..graph_context import build_graph_context_from_graph, build_short_graph_context

    try:
        from ..graph import build_graph_v2
        log("🔗 Building dependency graph...")
        _graph = build_graph_v2(str(root))
        result["graph_ctx"] = build_graph_context_from_graph(_graph)
        result["short_graph_ctx"] = build_short_graph_context(_graph)
        result["_graph"] = _graph
        module_count = len([n for n in _graph.nodes if n.node_type == "module"])
        edge_count = len([e for e in _graph.edges if e.edge_type in ("imports", "depends_on")])
        log(f"   ✅ Graph: {module_count} modules, {edge_count} dependencies")
    except Exception as e:
        log(f"   ⚠️  Graph analysis skipped: {e}")


def _build_semantic(root: Path, all_files: list, result: dict, log) -> None:
    from ..graph_context import build_semantic_context, format_facts_section

    try:
        log("🔍 Extracting semantic facts...")
        result["semantic_ctx"] = build_semantic_context(
            str(root), all_files,
            graph=result["_graph"],
            include_snippets=True,
        )
        from ..facts import extract_facts as _extract_facts
        _facts = _extract_facts(str(root), all_files)
        result["facts_ctx"] = format_facts_section(_facts)
        result["_facts"] = _facts
        if _facts:
            log(f"   ✅ Facts: {len(_facts)} items extracted")
        else:
            log(f"   ℹ️  No semantic facts found (project may not match patterns)")
    except Exception as e:
        log(f"   ⚠️  Semantic context extraction skipped: {e}")


def _build_api_surface(root: Path, all_files: list, result: dict, log) -> None:
    from ..graph_context import format_api_surface

    try:
        if all_files:
            api_surface_ctx = format_api_surface(
                str(root), all_files, graph=result["_graph"],
            )
            if api_surface_ctx:
                result["api_surface_ctx"] = api_surface_ctx
                log("   ✅ API Surface extracted for all chapters")
    except Exception as e:
        log(f"   ⚠️  API Surface extraction skipped: {e}")


def _build_doc_chunks(
    root: Path, all_files: list, repo_map: dict, result: dict, log,
) -> None:
    try:
        from ..intelligence.doc_chunks import (
            chunk_endpoints, chunk_data_models, chunk_mcp_tools,
            chunk_cli_commands, chunk_architecture, chunk_module_summary,
            build_all_ast_symbols,
        )
        log("🧩 Building documentation chunks (chunked mode)...")

        ast_symbols = build_all_ast_symbols(str(root), all_files)
        if ast_symbols:
            log(f"   ✅ AST symbols: {sum(len(v) for v in ast_symbols.values())} symbols from {len(ast_symbols)} files")

        _facts = result["_facts"]
        _build_info = repo_map.get("build_info", {})

        doc_chunks = {
            "endpoints": chunk_endpoints(_facts, ast_symbols),
            "data_models": chunk_data_models(_facts, ast_symbols),
            "mcp_tools": chunk_mcp_tools(ast_symbols, _facts),
            "cli_commands": chunk_cli_commands(_facts, ast_symbols),
            "architecture": chunk_architecture(result["graph_ctx"], _build_info),
        }

        module_summaries = []
        for file_path, symbols in list(ast_symbols.items())[:8]:
            summary = chunk_module_summary(file_path, symbols, max_lines=10)
            if summary:
                module_summaries.append(summary)
        doc_chunks["module_summaries"] = "\n\n".join(module_summaries) if module_summaries else ""

        result["doc_chunks"] = doc_chunks
        non_empty = sum(1 for v in doc_chunks.values() if v)
        log(f"   ✅ Chunks: {non_empty}/{len(doc_chunks)} non-empty")
    except Exception as e:
        log(f"   ⚠️  Doc chunks skipped: {e}")


def _build_facts_only(
    root: Path, all_files: list, repo_map: dict, result: dict, log,
) -> None:
    from ..graph_context import (
        build_facts_only_context, build_facts_only_context_for_chapter,
        filter_facts_for_chapter, format_facts_section,
    )

    try:
        from ..intelligence.compressor import compress_batch
        from ..graph_context import _compute_ranks
        from ..graph import is_test_file

        log("🔬 Facts-only mode: compressing top file signatures...")
        _fo_facts = result["_facts"]
        _fo_build_info = repo_map.get("build_info", {})
        _graph = result["_graph"]

        # Pick top files by PageRank — cap at 15
        _top_files = _select_top_files(_graph, all_files, _compute_ranks, is_test_file)

        # Read file contents for compression
        _contents: dict[str, str] = {}
        for fpath in _top_files:
            full_path = root / fpath
            if full_path.is_file():
                try:
                    _contents[fpath] = full_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass
        _fo_compressed = compress_batch(_contents) if _contents else {}
        if _fo_compressed:
            log(f"   ✅ Compressed {len(_fo_compressed)} file signatures")

        # Build per-chapter contexts
        fo_ctx: dict[str, str] = {}
        for _ch_file in [
            "01-overview.md", "02-quickstart.md", "04-core-mechanisms.md",
            "05-data-models.md", "06-api-reference.md", "07-dev-guide.md",
        ]:
            fo_ctx[_ch_file] = build_facts_only_context_for_chapter(
                _ch_file, str(root), all_files, _fo_facts,
                result["api_surface_ctx"], _fo_compressed, _fo_build_info,
            )

        # Architecture: filtered facts + short graph
        _arch_filtered = filter_facts_for_chapter("03-architecture.md", _fo_facts)
        _arch_facts_ctx = format_facts_section(_arch_filtered)
        _arch_parts = [p for p in [result["short_graph_ctx"], _arch_facts_ctx] if p]
        fo_ctx["03-architecture.md"] = "\n".join(_arch_parts).strip()

        fo_ctx["index.md"] = ""
        fo_ctx["_default"] = build_facts_only_context(
            str(root), all_files, _fo_facts,
            result["api_surface_ctx"], _fo_compressed, _fo_build_info,
        )

        result["fo_context_by_chapter"] = fo_ctx
        _total = sum(len(v) for v in fo_ctx.values())
        log(f"   ✅ Per-chapter facts-only context built ({len(fo_ctx)} chapters, {_total} total chars)")
    except Exception as e:
        log(f"   ⚠️  Facts-only context skipped: {e}")


def _select_top_files(graph, all_files, compute_ranks, is_test_file, limit=15):
    """Select top files by PageRank or connection count."""
    if graph is not None:
        ranks = compute_ranks(graph)
        module_ids = [
            n.id for n in graph.nodes
            if n.node_type == "module" and not is_test_file(n.id)
        ]
        if ranks:
            return sorted(module_ids, key=lambda f: ranks.get(f, 0), reverse=True)[:limit]
        connections: dict[str, int] = {}
        for e in graph.edges:
            if e.edge_type in ("imports", "depends_on"):
                connections[e.source] = connections.get(e.source, 0) + 1
                connections[e.target] = connections.get(e.target, 0) + 1
        return sorted(module_ids, key=lambda f: connections.get(f, 0), reverse=True)[:limit]
    return all_files[:limit]
