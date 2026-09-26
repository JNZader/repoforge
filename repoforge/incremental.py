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


def _norm_repo_path(path: str) -> str:
    """Compare repo-relative paths without a leading ./ or backslashes."""
    text = path.replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text


def stale_chapter_names(
    changed_files: list[str],
    consumed_by_chapter: dict[str, list[str]],
) -> list[str]:
    """Return chapters whose consumed files include a changed path.

    A chapter that did not consume a changed path stays current. This does
    not regenerate prose. Order follows ``consumed_by_chapter``.
    """
    changed = {_norm_repo_path(path) for path in changed_files if path.strip()}
    stale: list[str] = []
    for name, files in consumed_by_chapter.items():
        consumed = {_norm_repo_path(path) for path in files}
        if changed & consumed:
            stale.append(name)
    return stale


def files_cited_in_prompt(prompt: str, known_files: list[str]) -> list[str]:
    """Known repo paths that appear in ``prompt`` as whole paths.

    ``app/main.py`` does not match inside ``apps/server/app/main.py``.
    Result order follows ``known_files``.
    """
    cited: list[str] = []
    for path in known_files:
        if path and _path_is_cited(prompt, path):
            cited.append(path)
    return cited


def _path_is_cited(prompt: str, path: str) -> bool:
    start = 0
    while True:
        index = prompt.find(path, start)
        if index < 0:
            return False
        before = prompt[index - 1] if index else ""
        after_at = index + len(path)
        after = prompt[after_at] if after_at < len(prompt) else ""
        if before not in "/\\" and after not in "/_\\" and not after.isalnum():
            return True
        start = index + 1


def prompt_consumed_files(
    chapters: list[dict],
    known_files: list[str],
) -> dict[str, list[str]]:
    """Files cited in each chapter's graph context, not the module catalog.

    The overview prompt lists every scanned module. That catalog is the
    all-files guess again. Consumption is ``context_source``: the graph,
    facts, or API surface interpolated into the prompt. Chapters built
    before that field existed fall back to the full user prompt.
    """
    consumed: dict[str, list[str]] = {}
    for chapter in chapters:
        source = chapter.get("context_source")
        if source is None:
            source = chapter.get("user", "")
        consumed[chapter["file"]] = files_cited_in_prompt(source, known_files)
    return consumed


def recorded_consumed_files(
    chapters: list[dict],
    manifest: Optional[Manifest],
    guessed: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Prefer the files a chapter already recorded over a fresh guess.

    ``build_chapter_deps`` marks overview and architecture as depending on
    every scanned file. After a manifest exists, staleness uses the files
    that chapter actually consumed.
    """
    consumed: dict[str, list[str]] = {}
    for chapter in chapters:
        fname = chapter["file"]
        entry = None if manifest is None else manifest.chapters.get(fname)
        if entry is not None and entry.source_files:
            consumed[fname] = list(entry.source_files)
        else:
            consumed[fname] = list(guessed.get(fname, []))
    return consumed


def get_stale_chapters(
    chapters: list[dict],
    manifest: Optional[Manifest],
    changed_files: list[str],
    deps: dict[str, list[str]],
) -> list[dict]:
    """Return the subset of *chapters* that need regeneration.

    A chapter is stale if:
    - It has no entry in the manifest (new chapter).
    - Any file it consumed appears in *changed_files*.
    - The manifest is None (first run / corrupt manifest).

    ``deps`` is the consumed-file list. Callers that already have a
    manifest should pass :func:`recorded_consumed_files`, not a fresh
    all-files guess.
    """
    if manifest is None:
        return list(chapters)

    if not changed_files:
        # No files changed — nothing is stale
        return []

    consumed = {chapter["file"]: deps.get(chapter["file"], []) for chapter in chapters}
    stale_names = set(stale_chapter_names(changed_files, consumed))
    stale: list[dict] = []
    for chapter in chapters:
        fname = chapter["file"]
        if fname not in manifest.chapters or fname in stale_names:
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
