"""
docs_generator.py - Pipeline for generating technical documentation.

Flow:
  1. scan_repo()           → repo_map (deterministic, no LLM)
  2. Extract AST symbols + facts (deterministic, no LLM)
  3. Build pre-digested chunks per chapter type (deterministic, no LLM)
  4. get_chapter_prompts() → list of (file, system, user) per chapter
  5. llm.complete()        → markdown content per chapter
  6. write files           → docs/01-overview.md, etc.
  7. docsify.build()       → index.html, _sidebar.md, .nojekyll

Output is a Docsify-ready docs/ folder that works on GitHub Pages with zero config.

v8: Chunked documentation — each chapter gets ONLY the pre-digested data it needs,
not the entire project context. This reduces hallucination and token waste.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from .scanner import scan_repo, classify_complexity
from .llm import build_llm
from .docs_prompts import get_chapter_prompts
from .docsify import build_docsify_files
from .graph_context import (
    build_graph_context_from_graph,
    build_short_graph_context,
    build_semantic_context,
    format_api_surface,
    format_facts_section,
)


def generate_docs(
    working_dir: str = ".",
    output_dir: str = "docs",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    language: str = "English",
    project_name: Optional[str] = None,
    verbose: bool = True,
    dry_run: bool = False,
    complexity: str = "auto",
    chunked: bool = False,
    verify: bool = True,
    verify_model: Optional[str] = None,
    no_verify_docs: bool = False,
) -> dict:
    """
    Main entry point for documentation generation.

    Generates a Docsify-ready docs/ folder with:
      - index.md, 01-overview.md ... 07-dev-guide.md
      - index.html (Docsify)
      - _sidebar.md (navigation)
      - .nojekyll (GH Pages)

    Returns a summary dict with generated file paths and stats.
    """
    root = Path(working_dir).resolve()
    out = Path(output_dir) if Path(output_dir).is_absolute() else root / output_dir

    log = _make_logger(verbose)

    # ------------------------------------------------------------------
    # 1. Scan repo (deterministic, free)
    # ------------------------------------------------------------------
    log(f"📂 Scanning {root} ...")
    repo_map = scan_repo(str(root))

    # Apply repoforge.yaml overrides
    cfg = repo_map.get("repoforge_config", {})
    if cfg.get("language") and language == "English":
        language = cfg["language"]
    if cfg.get("model") and model is None:
        model = cfg["model"]
    if cfg.get("project_name") and project_name is None:
        project_name = cfg["project_name"]

    # Resolve complexity: CLI flag > config file > auto
    if complexity == "auto":
        complexity = cfg.get("complexity", "auto")
    cx = classify_complexity(repo_map, override=complexity)

    stats = repo_map.get("stats", {})
    rg = stats.get("rg_version", None)
    rg_status = f"ripgrep {rg}" if rg else "fallback mode"
    total_files = stats.get("total_files", "?")

    layers = list(repo_map["layers"].keys())
    log(f"🗂  Layers: {', '.join(layers)}")
    log(f"🔧 Stack:  {', '.join(repo_map['tech_stack']) or 'unknown'}")
    log(f"📊 Files:  {total_files}  [{rg_status}]")
    log(f"📐 Complexity: {cx['size']} → max_chapters={cx['max_chapters']}")

    # ------------------------------------------------------------------
    # 2. Resolve project name
    # ------------------------------------------------------------------
    if not project_name:
        project_name = _infer_project_name(root, repo_map)
    log(f"📝 Project: {project_name}")

    # ------------------------------------------------------------------
    # 3. Build LLM
    # ------------------------------------------------------------------
    llm = build_llm(model=model, api_key=api_key, api_base=api_base)
    log(f"🤖 Model:  {llm.model}")
    log(f"🌐 Language: {language}")

    # ------------------------------------------------------------------
    # 3b. Build dependency graph + semantic context (cached, used by all chapters)
    # ------------------------------------------------------------------
    graph_ctx = ""
    short_graph_ctx = ""
    semantic_ctx = ""
    facts_ctx = ""
    try:
        from .graph import build_graph_v2
        log(f"🔗 Building dependency graph...")
        _graph = build_graph_v2(str(root))
        graph_ctx = build_graph_context_from_graph(_graph)
        short_graph_ctx = build_short_graph_context(_graph)
        module_count = len([n for n in _graph.nodes if n.node_type == "module"])
        edge_count = len([e for e in _graph.edges if e.edge_type in ("imports", "depends_on")])
        log(f"   ✅ Graph: {module_count} modules, {edge_count} dependencies")
    except Exception as e:
        log(f"   ⚠️  Graph analysis skipped: {e}")
        _graph = None

    # Build semantic context (graph + facts + snippets)
    try:
        all_files = [
            m["path"]
            for layer in repo_map["layers"].values()
            for m in layer.get("modules", [])
        ]
        log(f"🔍 Extracting semantic facts...")
        # Full context for architecture chapter (includes snippets)
        semantic_ctx = build_semantic_context(
            str(root), all_files,
            graph=_graph if '_graph' in dir() else None,
            include_snippets=True,
        )
        # Facts-only context for other chapters (no snippets to save tokens)
        from .facts import extract_facts as _extract_facts
        _facts = _extract_facts(str(root), all_files)
        facts_ctx = format_facts_section(_facts)
        if _facts:
            log(f"   ✅ Facts: {len(_facts)} items extracted")
        else:
            log(f"   ℹ️  No semantic facts found (project may not match patterns)")
    except Exception as e:
        log(f"   ⚠️  Semantic context extraction skipped: {e}")

    # ------------------------------------------------------------------
    # 3c. Extract API Surface separately for non-architecture chapters
    # ------------------------------------------------------------------
    api_surface_ctx = ""
    try:
        if all_files:
            api_surface_ctx = format_api_surface(
                str(root), all_files,
                graph=_graph if '_graph' in dir() else None,
            )
            if api_surface_ctx:
                log(f"   ✅ API Surface extracted for all chapters")
    except Exception as e:
        log(f"   ⚠️  API Surface extraction skipped: {e}")

    # ------------------------------------------------------------------
    # 3d. Build pre-digested chunks for focused chapter generation
    #      (only when --chunked flag is set)
    # ------------------------------------------------------------------
    doc_chunks = {}
    if chunked:
        try:
            from .intelligence.doc_chunks import (
                chunk_endpoints,
                chunk_data_models,
                chunk_mcp_tools,
                chunk_cli_commands,
                chunk_architecture,
                chunk_module_summary,
                build_all_ast_symbols,
            )
            log(f"🧩 Building documentation chunks (chunked mode)...")

            # Extract AST symbols once for all files
            ast_symbols = build_all_ast_symbols(str(root), all_files)
            if ast_symbols:
                log(f"   ✅ AST symbols: {sum(len(v) for v in ast_symbols.values())} symbols from {len(ast_symbols)} files")

            # Build per-chapter chunks
            _facts_list = _facts if '_facts' in dir() else []
            _build_info = repo_map.get("build_info", {})

            endpoints_chunk = chunk_endpoints(_facts_list, ast_symbols)
            models_chunk = chunk_data_models(_facts_list, ast_symbols)
            mcp_chunk = chunk_mcp_tools(ast_symbols, _facts_list)
            cli_chunk = chunk_cli_commands(_facts_list, ast_symbols)
            arch_chunk = chunk_architecture(graph_ctx, _build_info)

            # Module summaries for overview — cap at 8 most important files
            # to avoid blowing token budgets on small models
            module_summaries = []
            for file_path, symbols in list(ast_symbols.items())[:8]:
                summary = chunk_module_summary(file_path, symbols, max_lines=10)
                if summary:
                    module_summaries.append(summary)
            modules_chunk = "\n\n".join(module_summaries) if module_summaries else ""

            doc_chunks = {
                "endpoints": endpoints_chunk,
                "data_models": models_chunk,
                "mcp_tools": mcp_chunk,
                "cli_commands": cli_chunk,
                "architecture": arch_chunk,
                "module_summaries": modules_chunk,
            }

            non_empty = sum(1 for v in doc_chunks.values() if v)
            log(f"   ✅ Chunks: {non_empty}/{len(doc_chunks)} non-empty")
        except Exception as e:
            log(f"   ⚠️  Doc chunks skipped: {e}")
    else:
        log(f"📄 Full-context mode (default). Use --chunked for per-chapter chunks.")

    # ------------------------------------------------------------------
    # 4. Get chapter list (trimmed by complexity)
    # ------------------------------------------------------------------
    # Architecture chapter gets FULL semantic context (graph + facts + snippets)
    # Other chapters get facts + API Surface + short graph (no snippets to save tokens)
    _arch_context = semantic_ctx or graph_ctx
    _other_parts = [p for p in [facts_ctx, api_surface_ctx, short_graph_ctx] if p]
    _other_context = "\n".join(_other_parts).strip() if _other_parts else ""

    all_chapters = get_chapter_prompts(
        repo_map, language, project_name,
        graph_context=_arch_context,
        short_graph_context=_other_context,
        doc_chunks=doc_chunks,
    )
    max_ch = cx["max_chapters"]
    if len(all_chapters) > max_ch:
        # Always keep index + first chapters; trim type-specific ones from the end
        chapters = all_chapters[:max_ch]
        log(f"\n📋 Chapters to generate: {len(chapters)} (capped from {len(all_chapters)} by {cx['size']} complexity)")
    else:
        chapters = all_chapters
        log(f"\n📋 Chapters to generate: {len(chapters)}")
    for c in chapters:
        log(f"   • {c['file']} — {c['title']}")

    if dry_run:
        log("\n🔍 DRY RUN — no LLM calls, no files written")
        return {
            "project_name": project_name,
            "language": language,
            "chapters": [c["file"] for c in chapters],
            "dry_run": True,
        }

    # ------------------------------------------------------------------
    # 5. Prepare post-processing pipeline (Stage D + Stage C)
    # ------------------------------------------------------------------
    do_post_process = not no_verify_docs
    do_verify = verify and not no_verify_docs

    # Resolve facts/build_info/ast_symbols for post-processing
    _pp_facts: list = _facts if '_facts' in dir() else []
    _pp_build_info = None
    _pp_ast_symbols: dict | None = None

    if do_post_process or do_verify:
        try:
            from .intelligence.build_parser import parse_build_files
            _pp_build_info = parse_build_files(str(root))
        except Exception as e:
            log(f"   ⚠️  Build info for post-processing unavailable: {e}")

        if chunked and 'ast_symbols' in dir() and ast_symbols:
            _pp_ast_symbols = ast_symbols
        elif do_post_process:
            try:
                from .intelligence.doc_chunks import build_all_ast_symbols
                _all_files = [
                    m["path"]
                    for layer in repo_map["layers"].values()
                    for m in layer.get("modules", [])
                ]
                _pp_ast_symbols = build_all_ast_symbols(str(root), _all_files)
            except Exception:
                pass

    all_corrections_log: list[dict] = []

    # ------------------------------------------------------------------
    # 6. Generate each chapter
    # ------------------------------------------------------------------
    out.mkdir(parents=True, exist_ok=True)
    generated = []
    errors = []

    log("\n✍️  Generating documentation...\n")
    for i, chapter in enumerate(chapters, 1):
        subdir = chapter.get("subdir")
        display = f"{subdir}/{chapter['file']}" if subdir else chapter["file"]
        log(f"[{i}/{len(chapters)}] {display} — {chapter['title']} ...", end=" ")
        try:
            content = llm.complete(chapter["user"], system=chapter["system"])
            content = content.strip() + "\n"
            log("✅", end="")

            # Stage D: Deterministic post-processing
            if do_post_process:
                try:
                    from .intelligence.post_process import post_process_chapter
                    content, d_corrections = post_process_chapter(
                        content=content,
                        facts=_pp_facts,
                        build_info=_pp_build_info,
                        ast_symbols=_pp_ast_symbols,
                        chapter_file=chapter["file"],
                    )
                    if d_corrections:
                        log(f" 🔧D:{len(d_corrections)}", end="")
                        all_corrections_log.append({
                            "file": chapter["file"],
                            "stage": "D",
                            "corrections": [
                                {"original": c.original, "corrected": c.corrected,
                                 "reason": c.reason, "line": c.line}
                                for c in d_corrections
                            ],
                        })
                except Exception as e:
                    log(f" ⚠️D:{e}", end="")

            # Stage C: LLM verification
            if do_verify:
                try:
                    from .intelligence.verifier import verify_chapter
                    content, v_issues = verify_chapter(
                        chapter_content=content,
                        facts=_pp_facts,
                        ast_symbols=_pp_ast_symbols,
                        llm=llm,
                        model=verify_model,
                    )
                    if v_issues:
                        log(f" 🔍C:{len(v_issues)}", end="")
                        all_corrections_log.append({
                            "file": chapter["file"],
                            "stage": "C",
                            "issues": v_issues,
                        })
                except Exception as e:
                    log(f" ⚠️C:{e}", end="")

            log("")  # newline after all status indicators

            # Write to per-layer subdir for monorepos, root otherwise
            if subdir:
                chapter_dir = out / subdir
                chapter_dir.mkdir(parents=True, exist_ok=True)
                path = chapter_dir / chapter["file"]
            else:
                path = out / chapter["file"]
            path.write_text(content, encoding="utf-8")
            generated.append(str(path))
        except Exception as e:
            errors.append({"file": chapter["file"], "error": str(e)})
            log(f"❌ {e}")

    # ------------------------------------------------------------------
    # 6b. Write corrections log
    # ------------------------------------------------------------------
    if all_corrections_log:
        import json as _json
        corrections_path = out / "_corrections_log.json"
        corrections_path.write_text(
            _json.dumps(all_corrections_log, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log(f"\n📋 Corrections log: {_rel(corrections_path, root)}")

    # ------------------------------------------------------------------
    # 7. Generate Docsify files (deterministic, no LLM)
    # ------------------------------------------------------------------
    log("\n🌐 Building Docsify files...")
    docsify_files = build_docsify_files(
        output_dir=out,
        project_name=project_name,
        chapters=[c for c in chapters if c["file"] in [p.split("/")[-1] for p in generated]],
        language=language,
    )
    for f in docsify_files:
        log(f"   ✅ {_rel(f, root)}")

    # ------------------------------------------------------------------
    # 8. Summary
    # ------------------------------------------------------------------
    total = len(generated)
    verify_status = ""
    if no_verify_docs:
        verify_status = " (verification disabled)"
    elif do_verify:
        verify_status = f" (verified with {verify_model or 'Phi-4'})"
    elif do_post_process:
        verify_status = " (deterministic corrections only)"

    log(f"\n🎉 Done! {total} chapters + {len(docsify_files)} Docsify files{verify_status}")
    log(f"   Output: {_rel(out, root)}/")
    if all_corrections_log:
        total_fixes = sum(
            len(entry.get("corrections", entry.get("issues", [])))
            for entry in all_corrections_log
        )
        log(f"   📋 {total_fixes} correction(s) applied across {len(all_corrections_log)} chapter(s)")
    log("\n📖 To preview locally:")
    log(f"   npx serve {_rel(out, root)}   (or: python3 -m http.server 8000 --directory {_rel(out, root)})")
    log("\n🚀 To publish on GitHub Pages:")
    log(f"   Push to GitHub → Settings → Pages → Source: /{_rel(out, root)} on main branch")

    if errors:
        log(f"\n⚠️  {len(errors)} chapter(s) failed:")
        for e in errors:
            log(f"   ❌ {e['file']}: {e['error']}")

    return {
        "project_name": project_name,
        "language": language,
        "output_dir": str(out),
        "chapters_generated": generated,
        "docsify_files": docsify_files,
        "errors": errors,
        "corrections": all_corrections_log,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rel(path, root) -> str:
    """Safe relative path — falls back to absolute if outside root."""
    try:
        return str(Path(path).resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _infer_project_name(root: Path, repo_map: dict) -> str:
    """Infer project name from config files or directory name."""
    import json

    # Try package.json
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text())
            name = data.get("name", "")
            if name and name != "":
                return _prettify_name(name)
        except Exception as e:
            logger.debug("Failed to read project name from package.json: %s", e)

    # Try pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text()
            for line in content.split("\n"):
                if line.strip().startswith("name"):
                    # name = "my-project" or name = 'my-project'
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        name = parts[1].strip().strip('"\'')
                        if name:
                            return _prettify_name(name)
        except Exception as e:
            logger.debug("Failed to read project name from pyproject.toml: %s", e)

    # Try go.mod
    gomod = root / "go.mod"
    if gomod.exists():
        try:
            first_line = gomod.read_text().split("\n")[0]
            # "module github.com/user/project"
            parts = first_line.split("/")
            if parts:
                return _prettify_name(parts[-1].strip())
        except Exception as e:
            logger.debug("Failed to read project name from go.mod: %s", e)

    # Fall back to directory name
    return _prettify_name(root.name)


def _prettify_name(name: str) -> str:
    """Convert kebab-case or snake_case to Title Case."""
    return name.replace("-", " ").replace("_", " ").title()


def _make_logger(verbose: bool):
    """Return a logger function. Supports end= kwarg like print."""
    if verbose:
        def log(msg: str = "", end: str = "\n"):
            print(msg, end=end, file=sys.stderr, flush=True)
        return log
    return lambda msg="", **kwargs: None
