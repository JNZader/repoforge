"""
docs_generator.py - Orchestrator for the documentation generation pipeline.

Delegates to pipeline/ stages for context building, chapter generation,
post-processing, and file writing. This module is the thin coordinator.

Flow:
  1. scan_repo()                          → repo_map
  2. pipeline.context.build_all_contexts  → contexts dict
  3. get_chapter_prompts()                → list of chapter dicts
  4. pipeline.generate per chapter        → content
  5. pipeline.write                       → docs/ folder
"""

import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from .docs_prompts import get_chapter_prompts
from .incremental import (
    ChapterEntry,
    Manifest,
    build_chapter_deps,
    content_hash,
    get_changed_files,
    get_git_sha,
    get_stale_chapters,
    now_iso,
)
from .incremental import (
    load_manifest as _load_manifest,
)
from .llm import build_llm
from .pipeline.context import build_all_contexts
from .pipeline.generate import generate_chapter, postprocess_chapter
from .pipeline.write import (
    _rel,
    write_chapter,
    write_corrections_log,
    write_docsify,
    write_manifest,
)
from .scanner import classify_complexity, scan_repo


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
    facts_only: bool = False,
    incremental: bool = False,
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
    # Stage 1: Scan repo
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

    # Resolve complexity
    if complexity == "auto":
        complexity = cfg.get("complexity", "auto")
    cx = classify_complexity(repo_map, override=complexity)

    stats = repo_map.get("stats", {})
    rg = stats.get("rg_version", None)
    total_files = stats.get("total_files", "?")
    log(f"🗂  Layers: {', '.join(repo_map['layers'].keys())}")
    log(f"🔧 Stack:  {', '.join(repo_map['tech_stack']) or 'unknown'}")
    log(f"📊 Files:  {total_files}  [{'ripgrep ' + rg if rg else 'fallback mode'}]")
    log(f"📐 Complexity: {cx['size']} → max_chapters={cx['max_chapters']}")

    # ------------------------------------------------------------------
    # Stage 2: Resolve project name + build LLM
    # ------------------------------------------------------------------
    if not project_name:
        project_name = _infer_project_name(root, repo_map)
    log(f"📝 Project: {project_name}")

    llm = build_llm(model=model, api_key=api_key, api_base=api_base)
    log(f"🤖 Model:  {llm.model}")
    log(f"🌐 Language: {language}")

    # ------------------------------------------------------------------
    # Stage 3: Build all contexts (graph, semantic, chunks, facts-only)
    # ------------------------------------------------------------------
    ctx = build_all_contexts(
        root, repo_map, log, chunked=chunked, facts_only=facts_only,
    )

    # ------------------------------------------------------------------
    # Stage 4: Get chapter list
    # ------------------------------------------------------------------
    _arch_context = ctx["semantic_ctx"] or ctx["graph_ctx"]
    _other_parts = [p for p in [ctx["facts_ctx"], ctx["api_surface_ctx"], ctx["short_graph_ctx"]] if p]
    _other_context = "\n".join(_other_parts).strip() if _other_parts else ""

    all_chapters = get_chapter_prompts(
        repo_map, language, project_name,
        graph_context=_arch_context,
        short_graph_context=_other_context,
        doc_chunks=ctx["doc_chunks"],
        facts_only_context_by_chapter=ctx["fo_context_by_chapter"],
        diagram_context=ctx.get("diagram_ctx", ""),
        dep_health_context=ctx.get("dep_health_ctx", ""),
    )
    max_ch = cx["max_chapters"]
    chapters = all_chapters[:max_ch] if len(all_chapters) > max_ch else all_chapters
    log(f"\n📋 Chapters to generate: {len(chapters)}" +
        (f" (capped from {len(all_chapters)} by {cx['size']} complexity)" if len(all_chapters) > max_ch else ""))
    for c in chapters:
        log(f"   • {c['file']} — {c['title']}")

    if dry_run:
        log("\n🔍 DRY RUN — no LLM calls, no files written")
        return {
            "project_name": project_name, "language": language,
            "chapters": [c["file"] for c in chapters], "dry_run": True,
        }

    # ------------------------------------------------------------------
    # Stage 4b: Incremental filtering (--incremental)
    # ------------------------------------------------------------------
    _git_sha = get_git_sha(root) if incremental else ""
    _manifest = None
    _chapter_deps: dict[str, list[str]] = {}
    skipped_chapters: list[str] = []

    if incremental:
        _manifest = _load_manifest(out)
        _chapter_deps = build_chapter_deps(repo_map, chapters)
        if _manifest is None:
            log("\n⚠️  No manifest found — full generation will run")
        else:
            changed = get_changed_files(root, _manifest.git_sha)
            if not changed and _manifest.git_sha == _git_sha:
                log("\n✅ No source files changed — nothing to regenerate")
                return {
                    "project_name": project_name, "language": language,
                    "output_dir": str(out), "chapters_generated": [],
                    "skipped": [c["file"] for c in chapters],
                    "incremental": True,
                }
            stale = get_stale_chapters(chapters, _manifest, changed, _chapter_deps)
            skipped_chapters = [c["file"] for c in chapters if c not in stale]
            if skipped_chapters:
                log(f"\n♻️  Incremental: {len(stale)} stale, {len(skipped_chapters)} skipped")
                for s in skipped_chapters:
                    log(f"   ⏭  {s}")
            chapters = stale

    # ------------------------------------------------------------------
    # Stage 5: Prepare post-processing state
    # ------------------------------------------------------------------
    do_post_process = not no_verify_docs
    do_verify = verify and not no_verify_docs
    _pp_facts = ctx["_facts"]
    _pp_build_info = _load_build_info(root, do_post_process, do_verify, log)
    _pp_ast_symbols = _load_ast_symbols(root, repo_map, chunked, do_post_process, log)

    # ------------------------------------------------------------------
    # Stage 6: Generate each chapter
    # ------------------------------------------------------------------
    out.mkdir(parents=True, exist_ok=True)
    generated = []
    errors = []
    all_corrections: list[dict] = []

    log("\n✍️  Generating documentation...\n")
    for i, chapter in enumerate(chapters, 1):
        subdir = chapter.get("subdir")
        display = f"{subdir}/{chapter['file']}" if subdir else chapter["file"]
        log(f"[{i}/{len(chapters)}] {display} — {chapter['title']} ...", end=" ")
        try:
            content = generate_chapter(llm, chapter, log)
            log("✅", end="")

            content, corr = postprocess_chapter(
                content, chapter,
                facts=_pp_facts, build_info=_pp_build_info,
                ast_symbols=_pp_ast_symbols,
                do_post_process=do_post_process, do_verify=do_verify,
                llm=llm, verify_model=verify_model, log=log,
            )
            all_corrections.extend(corr)
            log("")

            path = write_chapter(content, chapter, out)
            generated.append(path)
        except Exception as e:
            errors.append({"file": chapter["file"], "error": str(e)})
            log(f"❌ {e}")

    # ------------------------------------------------------------------
    # Stage 7: Write corrections log + Docsify files
    # ------------------------------------------------------------------
    write_corrections_log(all_corrections, out, root, log)
    docsify_files = write_docsify(out, project_name, chapters, generated, language, root, log)

    # ------------------------------------------------------------------
    # Stage 7b: Write manifest (for incremental support)
    # ------------------------------------------------------------------
    _write_gen_manifest(out, root, _git_sha, _manifest, _chapter_deps, generated, log)

    # ------------------------------------------------------------------
    # Stage 8: Summary
    # ------------------------------------------------------------------
    _print_summary(log, generated, docsify_files, all_corrections,
                   no_verify_docs, do_verify, verify_model, out, root, errors)

    return {
        "project_name": project_name,
        "language": language,
        "output_dir": str(out),
        "chapters_generated": generated,
        "docsify_files": docsify_files,
        "errors": errors,
        "corrections": all_corrections,
        "skipped": skipped_chapters,
        "incremental": incremental,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_build_info(root, do_post_process, do_verify, log):
    if not (do_post_process or do_verify):
        return None
    try:
        from .intelligence.build_parser import parse_build_files
        return parse_build_files(str(root))
    except Exception as e:
        log(f"   ⚠️  Build info for post-processing unavailable: {e}")
        return None


def _load_ast_symbols(root, repo_map, chunked, do_post_process, log):
    if not do_post_process:
        return None
    try:
        from .intelligence.doc_chunks import build_all_ast_symbols
        _all_files = [
            m["path"]
            for layer in repo_map["layers"].values()
            for m in layer.get("modules", [])
        ]
        return build_all_ast_symbols(str(root), _all_files)
    except Exception:
        return None


def _infer_project_name(root: Path, repo_map: dict) -> str:
    """Infer project name from config files or directory name."""
    import json

    for name_source, parser in [
        (root / "package.json", lambda p: json.loads(p.read_text()).get("name", "")),
        (root / "pyproject.toml", lambda p: _parse_toml_name(p)),
        (root / "go.mod", lambda p: p.read_text().split("\n")[0].split("/")[-1].strip()),
    ]:
        if name_source.exists():
            try:
                name = parser(name_source)
                if name:
                    return _prettify_name(name)
            except Exception as e:
                logger.debug("Failed to read project name from %s: %s", name_source.name, e)

    return _prettify_name(root.name)


def _parse_toml_name(path: Path) -> str:
    for line in path.read_text().split("\n"):
        if line.strip().startswith("name"):
            parts = line.split("=", 1)
            if len(parts) == 2:
                return parts[1].strip().strip('"\'')
    return ""


def _prettify_name(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").title()


def _write_gen_manifest(out, root, git_sha, old_manifest, chapter_deps, generated, log):
    """Build and persist the dependency manifest after generation."""
    ts = now_iso()

    # Start from old manifest entries (preserves skipped chapters)
    manifest = Manifest(
        git_sha=git_sha or get_git_sha(root),
        generated_at=ts,
        chapters=(old_manifest.chapters.copy() if old_manifest else {}),
    )

    # Update entries for chapters that were (re)generated this run
    for gen_path in generated:
        fname = Path(gen_path).name
        try:
            text = Path(gen_path).read_text(encoding="utf-8")
        except OSError:
            text = ""
        manifest.chapters[fname] = ChapterEntry(
            source_files=chapter_deps.get(fname, []),
            content_hash=content_hash(text),
            generated_at=ts,
        )

    write_manifest(out, manifest)
    log(f"\n📦 Manifest written: {_rel(out / '.manifest.json', root)}")


def _make_logger(verbose: bool):
    if verbose:
        def log(msg: str = "", end: str = "\n"):
            print(msg, end=end, file=sys.stderr, flush=True)
        return log
    return lambda msg="", **kwargs: None


def _print_summary(log, generated, docsify_files, corrections,
                   no_verify_docs, do_verify, verify_model, out, root, errors):
    total = len(generated)
    verify_status = ""
    if no_verify_docs:
        verify_status = " (verification disabled)"
    elif do_verify:
        verify_status = f" (verified with {verify_model or 'Phi-4'})"
    elif not no_verify_docs:
        verify_status = " (deterministic corrections only)"

    log(f"\n🎉 Done! {total} chapters + {len(docsify_files)} Docsify files{verify_status}")

    try:
        rel_out = str(out.relative_to(root))
    except ValueError:
        rel_out = str(out)
    log(f"   Output: {rel_out}/")

    if corrections:
        total_fixes = sum(
            len(entry.get("corrections", entry.get("issues", [])))
            for entry in corrections
        )
        log(f"   📋 {total_fixes} correction(s) applied across {len(corrections)} chapter(s)")

    log(f"\n📖 To preview locally:")
    log(f"   npx serve {rel_out}   (or: python3 -m http.server 8000 --directory {rel_out})")
    log(f"\n🚀 To publish on GitHub Pages:")
    log(f"   Push to GitHub → Settings → Pages → Source: /{rel_out} on main branch")

    if errors:
        log(f"\n⚠️  {len(errors)} chapter(s) failed:")
        for e in errors:
            log(f"   ❌ {e['file']}: {e['error']}")
