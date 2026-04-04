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
    embed_diagrams: bool = False,
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
        "diagram_ctx": "",
        "semantic_ctx": "",
        "facts_ctx": "",
        "api_surface_ctx": "",
        "doc_chunks": {},
        "fo_context_by_chapter": None,
        "_graph": None,
        "_facts": [],
        "_all_files": all_files,
        "dep_health_ctx": "",
        "coverage_ctx": "",
    }

    # 3b. Build dependency graph
    _build_graph(root, result, log)

    # 3b'. Build diagrams from graph
    _build_diagrams(root, all_files, result, log, force=embed_diagrams)

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

    # 3f. Build dependency health context
    _build_dep_health(root, result, log)

    # 3g. Build coverage context
    _build_coverage(root, result, log)

    return result


def _build_diagrams(root: Path, all_files: list, result: dict, log, *, force: bool = False) -> None:
    """Build Mermaid architecture diagrams from the graph (if available).

    When force=True, attempts to build a graph even if one hasn't been built yet
    (e.g., when --diagrams flag is passed). Guarantees a diagram_ctx is set
    or an error is logged.
    """
    _graph = result.get("_graph")

    if _graph is None:
        if not force:
            return
        # --diagrams flag: attempt to build graph on demand
        try:
            from ..graph import build_graph_v2
            log("🔗 Building dependency graph for diagrams...")
            _graph = build_graph_v2(str(root))
            result["_graph"] = _graph
            log("   ✅ Graph ready for diagram generation")
        except (ImportError, OSError, ValueError, RuntimeError) as e:
            log(f"   ⚠️  Graph build failed, diagrams will be limited: {e}")
            # Still proceed — generate_all_diagrams handles empty/None graph gracefully

    try:
        from ..diagrams import generate_all_diagrams
        log("📊 Generating architecture diagrams...")
        result["diagram_ctx"] = generate_all_diagrams(
            str(root), _graph, all_files,
        )
        log("   ✅ Diagrams generated")
    except (ImportError, OSError, ValueError, RuntimeError) as e:
        # ImportError: diagrams module missing; others: generation failures
        log(f"   ⚠️  Diagram generation skipped: {e}")


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
    except (ImportError, OSError, ValueError, RuntimeError) as e:
        # ImportError: graph module not available; others: graph build failures
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
    except (ImportError, OSError, ValueError, KeyError) as e:
        # ImportError: module missing; OSError: file read; ValueError/KeyError: data issues
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
    except (ImportError, OSError, ValueError, RuntimeError) as e:
        # API surface extraction failures — degrade gracefully
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
    except (ImportError, OSError, ValueError, KeyError) as e:
        # ImportError: doc_chunks module; OSError: file read; ValueError/KeyError: data issues
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
                except OSError:
                    pass  # File unreadable or deleted between check and read
        _fo_compressed = compress_batch(_contents) if _contents else {}
        if _fo_compressed:
            log(f"   ✅ Compressed {len(_fo_compressed)} file signatures")

        # Build per-chapter contexts for ALL known chapter files.
        # This covers universal chapters AND adaptive chapters from any project type
        # (infra_devops, cli_tool, library_sdk, etc.) to avoid falling back to
        # the _default context which may exceed GitHub Models' 8K token cap.
        _all_chapter_files = [
            # Universal
            "01-overview.md", "02-quickstart.md", "04-core-mechanisms.md",
            "05-data-models.md", "06-api-reference.md", "07-dev-guide.md",
            # CLI
            "05-commands.md", "06-config.md",
            # Library
            "05-api-reference.md", "06-integration.md",
            # Data science
            "04-data-pipeline.md", "05-models.md", "06-experiments.md",
            # Frontend
            "05-components.md", "06-state.md",
            # Mobile
            "05-screens.md", "06-native.md",
            # Desktop
            "05-ui.md", "06-platform.md",
            # Infra/DevOps
            "04-resources.md", "05-variables.md", "06-deployment.md",
            # Monorepo
            "06b-service-map.md",
        ]
        fo_ctx: dict[str, str] = {}
        for _ch_file in _all_chapter_files:
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
    except (ImportError, OSError, ValueError, KeyError) as e:
        # ImportError: compressor/graph modules; OSError: file read; ValueError/KeyError: data issues
        log(f"   ⚠️  Facts-only context skipped: {e}")


def _build_dep_health(root: Path, result: dict, log) -> None:
    """Analyze dependency health and add markdown context."""
    try:
        from ..dep_health import analyze_dependency_health
        report = analyze_dependency_health(str(root))
        if report is not None:
            result["dep_health_ctx"] = report.to_markdown()
            log(
                f"📦 Dependency health: {report.ecosystem} — "
                f"{report.direct_count} direct, {report.transitive_count} transitive, "
                f"health={report.health_score}"
            )
        else:
            log("📦 Dependency health: no supported manifests found")
    except (ImportError, OSError, ValueError) as e:
        # ImportError: dep_health module; OSError: manifest file read; ValueError: parse errors
        log(f"   ⚠️  Dependency health analysis skipped: {e}")


def _build_coverage(root: Path, result: dict, log) -> None:
    """Detect and parse coverage reports, render as markdown context."""
    try:
        from ..coverage import auto_detect_and_parse, render_coverage_markdown
        reports = auto_detect_and_parse(str(root))
        if reports:
            total_files = sum(len(r.files) for r in reports)
            formats = ", ".join({r.source_format for r in reports})
            result["coverage_ctx"] = render_coverage_markdown(reports)
            log(f"📈 Coverage: {total_files} files from {formats}")
        else:
            log("📈 Coverage: no coverage reports found")
    except (ImportError, OSError, ValueError) as e:
        # ImportError: coverage module; OSError: report file read; ValueError: parse errors
        log(f"   ⚠️  Coverage analysis skipped: {e}")


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
