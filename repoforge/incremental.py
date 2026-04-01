"""
incremental.py - Incremental documentation generation support.

Tracks which source files feed which doc sections via a JSON manifest.
On re-run with --incremental, only regenerates docs for sections whose
source files changed (detected via git diff).

Manifest format (.manifest.json):
{
  "git_sha": "abc123...",
  "generated_at": "2026-03-31T12:00:00Z",
  "chapters": {
    "01-overview.md": {
      "source_files": ["repoforge/cli.py", ...],
      "content_hash": "sha256hex...",
      "generated_at": "2026-03-31T12:00:00Z"
    }
  }
}
"""

import hashlib
import json
import logging
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = ".manifest.json"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ChapterEntry:
    """Tracks a single generated chapter's provenance."""

    source_files: list[str] = field(default_factory=list)
    content_hash: str = ""
    generated_at: str = ""


@dataclass
class Manifest:
    """Root manifest tracking all generated chapters."""

    git_sha: str = ""
    generated_at: str = ""
    chapters: dict[str, ChapterEntry] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Manifest I/O
# ---------------------------------------------------------------------------


def load_manifest(out_dir: Path) -> Optional[Manifest]:
    """Load manifest from output directory. Returns None if missing or corrupt."""
    path = Path(out_dir) / MANIFEST_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        chapters = {}
        for fname, entry_data in data.get("chapters", {}).items():
            chapters[fname] = ChapterEntry(
                source_files=entry_data.get("source_files", []),
                content_hash=entry_data.get("content_hash", ""),
                generated_at=entry_data.get("generated_at", ""),
            )
        return Manifest(
            git_sha=data.get("git_sha", ""),
            generated_at=data.get("generated_at", ""),
            chapters=chapters,
        )
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Corrupt manifest at %s: %s — will regenerate all", path, exc)
        return None


def save_manifest(out_dir: Path, manifest: Manifest) -> Path:
    """Persist manifest to the output directory. Returns the written path."""
    path = Path(out_dir) / MANIFEST_FILENAME
    data = {
        "git_sha": manifest.git_sha,
        "generated_at": manifest.generated_at,
        "chapters": {
            fname: asdict(entry)
            for fname, entry in manifest.chapters.items()
        },
    }
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Git integration
# ---------------------------------------------------------------------------


def get_git_sha(repo_root: Path) -> str:
    """Return the current HEAD commit SHA, or empty string if git unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return ""


def get_changed_files(repo_root: Path, old_sha: str) -> list[str]:
    """Return list of files changed between *old_sha* and HEAD.

    Uses ``git diff --name-only``.  Returns an empty list if git is
    unavailable or the SHA is invalid (caller should treat as "everything
    changed").
    """
    if not old_sha:
        return []
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{old_sha}..HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("git diff failed — falling back to full regeneration")
    return []


# ---------------------------------------------------------------------------
# Chapter ↔ source mapping
# ---------------------------------------------------------------------------

# Chapters that depend on ALL source files (cross-cutting concerns).
_GLOBAL_CHAPTERS = frozenset({
    "index.md",
    "01-overview.md",
    "02-quickstart.md",
    "03-architecture.md",
    "07-dev-guide.md",
})


def build_chapter_deps(
    repo_map: dict,
    chapters: list[dict],
) -> dict[str, list[str]]:
    """Build a mapping of chapter filename → list of source file paths.

    * Global chapters (overview, architecture, quickstart, dev-guide, index)
      depend on **all** scanned source files.
    * Domain-specific / adaptive chapters depend on files from their most
      relevant layer(s), determined by keyword overlap between chapter
      title/description and layer name.
    * If no specific layer match is found, the chapter depends on all files
      (conservative — ensures it is regenerated when anything changes).
    """
    all_files = _all_source_files(repo_map)
    layers = repo_map.get("layers", {})

    # Pre-build per-layer file lists
    layer_files: dict[str, list[str]] = {}
    for layer_name, layer_data in layers.items():
        layer_files[layer_name] = [
            m["path"] for m in layer_data.get("modules", [])
        ]

    deps: dict[str, list[str]] = {}
    for chapter in chapters:
        fname = chapter["file"]
        if fname in _GLOBAL_CHAPTERS:
            deps[fname] = all_files
        else:
            matched = _match_chapter_to_layers(chapter, layer_files)
            deps[fname] = matched if matched else all_files
    return deps


def _all_source_files(repo_map: dict) -> list[str]:
    """Extract all source file paths from repo_map."""
    return [
        m["path"]
        for layer_data in repo_map.get("layers", {}).values()
        for m in layer_data.get("modules", [])
    ]


def _match_chapter_to_layers(
    chapter: dict,
    layer_files: dict[str, list[str]],
) -> list[str]:
    """Heuristic: match chapter to layers by keyword overlap."""
    text = (
        chapter.get("title", "") + " " + chapter.get("description", "")
    ).lower()

    # Keywords that map to common layer names
    _LAYER_KEYWORDS: dict[str, list[str]] = {
        "frontend": ["ui", "component", "page", "frontend", "client", "web", "screen"],
        "backend": ["api", "endpoint", "server", "handler", "controller", "backend", "service"],
        "shared": ["shared", "common", "core", "util", "lib", "type"],
        "infra": ["infra", "deploy", "docker", "ci", "terraform", "helm", "k8s"],
    }

    matched_files: list[str] = []
    for layer_name, files in layer_files.items():
        layer_lower = layer_name.lower()
        # Direct name match
        if layer_lower in text:
            matched_files.extend(files)
            continue
        # Keyword match
        for _canonical, keywords in _LAYER_KEYWORDS.items():
            if any(kw in layer_lower for kw in keywords):
                if any(kw in text for kw in keywords):
                    matched_files.extend(files)
                    break

    return matched_files


# ---------------------------------------------------------------------------
# Staleness detection
# ---------------------------------------------------------------------------


def get_stale_chapters(
    chapters: list[dict],
    manifest: Optional[Manifest],
    changed_files: list[str],
    deps: dict[str, list[str]],
) -> list[dict]:
    """Return the subset of *chapters* that need regeneration.

    A chapter is stale if:
    - It has no entry in the manifest (new chapter).
    - Any of its source file dependencies appear in *changed_files*.
    - The manifest is None (first run / corrupt manifest).
    """
    if manifest is None:
        return list(chapters)

    if not changed_files:
        # No files changed — nothing is stale
        return []

    changed_set = set(changed_files)
    stale: list[dict] = []
    for chapter in chapters:
        fname = chapter["file"]
        if fname not in manifest.chapters:
            stale.append(chapter)
            continue
        chapter_deps = set(deps.get(fname, []))
        if chapter_deps & changed_set:
            stale.append(chapter)
    return stale


# ---------------------------------------------------------------------------
# Content hashing
# ---------------------------------------------------------------------------


def content_hash(text: str) -> str:
    """SHA-256 hex digest of the given text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    """Current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()
