"""File watcher for incremental documentation regeneration.

Polls file system for changes (no external dependencies like watchdog).
Uses SHA-256 hashing to detect modifications accurately.

Usage:
    from repoforge.watch import FileWatcher
    watcher = FileWatcher(repo_root, extensions={".py", ".ts", ".go"})
    snapshot1 = watcher.snapshot()
    # ... time passes, files change ...
    snapshot2 = watcher.snapshot()
    events = watcher.diff(snapshot1, snapshot2)
    for event in events:
        print(f"{event.event_type}: {event.path}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .cache import hash_file

logger = logging.getLogger(__name__)

_DEFAULT_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb",
    ".cs", ".cpp", ".c", ".h", ".php", ".swift", ".kt",
}

_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", ".nuxt", ".mypy_cache", ".ruff_cache", ".pytest_cache",
}


@dataclass
class WatchEvent:
    """A file system change event."""

    path: str           # relative path
    event_type: str     # "added", "modified", "removed"


class FileWatcher:
    """Poll-based file watcher using content hashing."""

    def __init__(
        self,
        root: Path,
        extensions: set[str] | None = None,
    ) -> None:
        self._root = Path(root)
        self._extensions = extensions or _DEFAULT_EXTENSIONS

    def snapshot(self) -> dict[str, str]:
        """Take a snapshot of all tracked files. Returns {rel_path: sha256_hash}."""
        files: dict[str, str] = {}
        for path in sorted(self._root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in self._extensions:
                continue
            try:
                rel_parts = path.relative_to(self._root).parts
            except ValueError:
                continue
            if any(part in _SKIP_DIRS for part in rel_parts):
                continue
            try:
                rel = str(path.relative_to(self._root))
                files[rel] = hash_file(path)
            except Exception:
                logger.debug("Failed to hash %s", path)

        return files

    def diff(
        self,
        old: dict[str, str],
        new: dict[str, str],
    ) -> list[WatchEvent]:
        """Compare two snapshots and return change events."""
        events: list[WatchEvent] = []
        old_keys = set(old.keys())
        new_keys = set(new.keys())

        for path in sorted(new_keys - old_keys):
            events.append(WatchEvent(path=path, event_type="added"))

        for path in sorted(old_keys - new_keys):
            events.append(WatchEvent(path=path, event_type="removed"))

        for path in sorted(old_keys & new_keys):
            if old[path] != new[path]:
                events.append(WatchEvent(path=path, event_type="modified"))

        return events
