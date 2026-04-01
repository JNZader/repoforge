"""Pipeline Stage 6-7: Write generated chapters + Docsify files."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def write_chapter(content: str, chapter: dict, out: Path) -> str:
    """Write a single chapter to disk. Returns the output file path."""
    subdir = chapter.get("subdir")
    if subdir:
        chapter_dir = out / subdir
        chapter_dir.mkdir(parents=True, exist_ok=True)
        path = chapter_dir / chapter["file"]
    else:
        path = out / chapter["file"]
    path.write_text(content, encoding="utf-8")
    return str(path)


def write_corrections_log(corrections: list[dict], out: Path, root: Path, log) -> None:
    """Write the corrections/verification audit log as JSON."""
    if not corrections:
        return
    path = out / "_corrections_log.json"
    path.write_text(
        json.dumps(corrections, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log(f"\n📋 Corrections log: {_rel(path, root)}")


def write_docsify(out: Path, project_name: str, chapters: list[dict],
                  generated: list[str], language: str, root: Path, log) -> list[str]:
    """Generate Docsify files and return list of created file paths."""
    from ..docsify import build_docsify_files

    log("\n🌐 Building Docsify files...")
    generated_filenames = [p.split("/")[-1] for p in generated]
    docsify_files = build_docsify_files(
        output_dir=out,
        project_name=project_name,
        chapters=[c for c in chapters if c["file"] in generated_filenames],
        language=language,
    )
    for f in docsify_files:
        log(f"   ✅ {_rel(f, root)}")
    return docsify_files


def write_manifest(out: Path, manifest) -> Path:
    """Persist an incremental-docs manifest to the output directory.

    Delegates to :func:`repoforge.incremental.save_manifest`.
    """
    from ..incremental import save_manifest
    return save_manifest(out, manifest)


def _rel(path, root) -> str:
    """Safe relative path — falls back to absolute if outside root."""
    try:
        return str(Path(path).resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)
