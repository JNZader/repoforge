"""Caching & incremental generation support.

Provides content hashing, repo snapshots, snapshot diffing, and a
persistent cache store for LLM responses. Enables incremental doc
generation by only regenerating chapters affected by code changes.

Usage:
    from repoforge.cache import CacheStore, compute_repo_snapshot, diff_snapshots

    store = CacheStore(repo_root / ".repoforge-cache.json")
    old = store.load_snapshot()
    new = compute_repo_snapshot(repo_root)
    diff = diff_snapshots(old or {"files": {}}, new)
    # diff["added"], diff["removed"], diff["modified"]
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Extensions to include in snapshots (matches ripgrep SUPPORTED_EXTENSIONS + docs)
_SNAPSHOT_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb",
    ".cs", ".cpp", ".c", ".h", ".php", ".swift", ".kt",
    ".md", ".yaml", ".yml", ".toml", ".json",
}

_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", ".nuxt", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    ".tox", ".eggs",
}


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def hash_content(content: str) -> str:
    """SHA-256 hash of a string. Returns 64-char hex digest."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def hash_file(path: Path) -> str:
    """SHA-256 hash of a file's contents."""
    return hash_content(path.read_text(encoding="utf-8", errors="replace"))


# ---------------------------------------------------------------------------
# Repo snapshot
# ---------------------------------------------------------------------------


def compute_repo_snapshot(
    root: Path,
    extensions: set[str] | None = None,
) -> dict:
    """Walk the repo and compute SHA-256 hashes for all source files.

    Returns:
        {"files": {"relative/path.py": "sha256hex", ...}}
    """
    exts = extensions or _SNAPSHOT_EXTENSIONS
    files: dict[str, str] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in exts:
            continue

        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            continue

        if any(part in _SKIP_DIRS for part in rel_parts):
            continue

        try:
            files[str(path.relative_to(root))] = hash_file(path)
        except Exception:
            logger.debug("Failed to hash %s", path)

    return {"files": files}


# ---------------------------------------------------------------------------
# Snapshot diffing
# ---------------------------------------------------------------------------


def diff_snapshots(old: dict, new: dict) -> dict:
    """Compare two snapshots and return added/removed/modified file lists.

    Returns:
        {"added": [...], "removed": [...], "modified": [...]}
    """
    old_files = old.get("files", {})
    new_files = new.get("files", {})
    old_keys = set(old_files.keys())
    new_keys = set(new_files.keys())

    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    modified = sorted(
        f for f in old_keys & new_keys
        if old_files[f] != new_files[f]
    )

    return {"added": added, "removed": removed, "modified": modified}


# ---------------------------------------------------------------------------
# Persistent cache store
# ---------------------------------------------------------------------------


class CacheStore:
    """JSON-based cache persisted to disk.

    Stores:
    - Repo snapshot (file hashes for incremental detection)
    - LLM response cache (prompt hash → generated content)
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict = self._load_raw()

    def _load_raw(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.warning("Corrupt cache at %s, starting fresh", self._path)
        return {}

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # -- Snapshot -----------------------------------------------------------

    def save_snapshot(self, snapshot: dict) -> None:
        self._data["snapshot"] = snapshot
        self._persist()

    def load_snapshot(self) -> Optional[dict]:
        return self._data.get("snapshot")

    # -- LLM response cache -------------------------------------------------

    def save_llm_response(self, prompt_hash: str, content: str) -> None:
        if "llm_cache" not in self._data:
            self._data["llm_cache"] = {}
        self._data["llm_cache"][prompt_hash] = content
        self._persist()

    def get_llm_response(self, prompt_hash: str) -> Optional[str]:
        return self._data.get("llm_cache", {}).get(prompt_hash)
