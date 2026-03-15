"""
docs_generator.py - Pipeline for generating technical documentation.

Flow:
  1. scan_repo()           → repo_map (deterministic, no LLM)
  2. get_chapter_prompts() → list of (file, system, user) per chapter
  3. llm.complete()        → markdown content per chapter
  4. write files           → docs/01-overview.md, etc.
  5. docsify.build()       → index.html, _sidebar.md, .nojekyll

Output is a Docsify-ready docs/ folder that works on GitHub Pages with zero config.
"""

import sys
from pathlib import Path
from typing import Optional

from .scanner import scan_repo
from .llm import build_llm
from .docs_prompts import get_chapter_prompts
from .docsify import build_docsify_files


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

    stats = repo_map.get("stats", {})
    rg = stats.get("rg_version", None)
    rg_status = f"ripgrep {rg}" if rg else "fallback mode"
    total_files = stats.get("total_files", "?")

    layers = list(repo_map["layers"].keys())
    log(f"🗂  Layers: {', '.join(layers)}")
    log(f"🔧 Stack:  {', '.join(repo_map['tech_stack']) or 'unknown'}")
    log(f"📊 Files:  {total_files}  [{rg_status}]")

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
    # 4. Get chapter list
    # ------------------------------------------------------------------
    chapters = get_chapter_prompts(repo_map, language, project_name)
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
    # 5. Generate each chapter
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
            # Write to per-layer subdir for monorepos, root otherwise
            if subdir:
                chapter_dir = out / subdir
                chapter_dir.mkdir(parents=True, exist_ok=True)
                path = chapter_dir / chapter["file"]
            else:
                path = out / chapter["file"]
            path.write_text(content, encoding="utf-8")
            generated.append(str(path))
            log("✅")
        except Exception as e:
            errors.append({"file": chapter["file"], "error": str(e)})
            log(f"❌ {e}")

    # ------------------------------------------------------------------
    # 6. Generate Docsify files (deterministic, no LLM)
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
    # 7. Summary
    # ------------------------------------------------------------------
    total = len(generated)
    log(f"\n🎉 Done! {total} chapters + {len(docsify_files)} Docsify files")
    log(f"   Output: {_rel(out, root)}/")
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
        except Exception:
            pass

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
        except Exception:
            pass

    # Try go.mod
    gomod = root / "go.mod"
    if gomod.exists():
        try:
            first_line = gomod.read_text().split("\n")[0]
            # "module github.com/user/project"
            parts = first_line.split("/")
            if parts:
                return _prettify_name(parts[-1].strip())
        except Exception:
            pass

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
