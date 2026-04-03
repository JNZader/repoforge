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

Watch mode (continuous regeneration):
    from repoforge.watch import watch_docs
    watch_docs(working_dir=".", output_dir="docs", interval=2.0, model="claude-haiku-3-5")
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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
            except OSError:
                # File may have been deleted or be unreadable between snapshot and hash
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


# ---------------------------------------------------------------------------
# Watch-mode loop for docs regeneration
# ---------------------------------------------------------------------------


def _format_events(events: list[WatchEvent]) -> str:
    """Format change events for console output."""
    lines: list[str] = []
    icons = {"added": "+", "modified": "~", "removed": "-"}
    for ev in events:
        lines.append(f"  {icons.get(ev.event_type, '?')} {ev.path}")
    return "\n".join(lines)


def watch_docs(
    working_dir: str = ".",
    output_dir: str = "docs",
    interval: float = 2.0,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    language: str = "English",
    project_name: Optional[str] = None,
    verbose: bool = True,
    complexity: str = "auto",
    chunked: bool = False,
    verify: bool = True,
    verify_model: Optional[str] = None,
    no_verify_docs: bool = False,
    facts_only: bool = False,
) -> None:
    """Run continuous watch loop: poll for changes, regenerate stale chapters.

    Uses :class:`FileWatcher` for change detection and delegates to
    :func:`generate_docs` with ``incremental=True`` for selective regeneration.

    The loop runs until interrupted with ``Ctrl+C``.
    """
    from .docs_generator import generate_docs  # lazy to avoid circular

    root = Path(working_dir).resolve()
    watcher = FileWatcher(root)
    prev_snapshot = watcher.snapshot()

    _log = _make_watch_logger(verbose)
    _log(f"\n\U0001F440 Watch mode active — polling every {interval}s")
    _log(f"   Root: {root}")
    _log(f"   Output: {output_dir}")
    _log(f"   Tracking {len(prev_snapshot)} source files")
    _log("   Press Ctrl+C to stop.\n")

    # Initial full generation (incremental will skip unchanged)
    try:
        _log("\U0001F680 Running initial documentation generation...")
        generate_docs(
            working_dir=working_dir,
            output_dir=output_dir,
            model=model,
            api_key=api_key,
            api_base=api_base,
            language=language,
            project_name=project_name,
            verbose=verbose,
            dry_run=False,
            complexity=complexity,
            chunked=chunked,
            verify=verify,
            verify_model=verify_model,
            no_verify_docs=no_verify_docs,
            facts_only=facts_only,
            incremental=True,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        # OSError: file system errors; ValueError: config/parse errors; RuntimeError: LLM/pipeline errors
        _log(f"\u274C Initial generation failed: {exc}")

    _log(f"\n\u23F3 Watching for changes (interval={interval}s)...\n")

    try:
        while True:
            time.sleep(interval)

            new_snapshot = watcher.snapshot()
            events = watcher.diff(prev_snapshot, new_snapshot)

            if not events:
                continue

            _log(f"\U0001F4C1 Detected {len(events)} change(s):")
            _log(_format_events(events))

            changed_paths = [ev.path for ev in events]
            _log(f"\u267B\uFE0F  Regenerating affected chapters...")

            try:
                result = generate_docs(
                    working_dir=working_dir,
                    output_dir=output_dir,
                    model=model,
                    api_key=api_key,
                    api_base=api_base,
                    language=language,
                    project_name=project_name,
                    verbose=verbose,
                    dry_run=False,
                    complexity=complexity,
                    chunked=chunked,
                    verify=verify,
                    verify_model=verify_model,
                    no_verify_docs=no_verify_docs,
                    facts_only=facts_only,
                    incremental=True,
                )
                gen = result.get("chapters_generated", [])
                skipped = result.get("skipped", [])
                if gen:
                    _log(f"\u2705 Regenerated {len(gen)} chapter(s), "
                         f"skipped {len(skipped)}")
                else:
                    _log("\u2705 No chapters needed regeneration")
            except (OSError, ValueError, RuntimeError) as exc:
                # OSError: file system errors; ValueError: config/parse errors; RuntimeError: LLM/pipeline errors
                _log(f"\u274C Regeneration failed: {exc}")

            prev_snapshot = new_snapshot
            _log(f"\n\u23F3 Watching for changes...\n")

    except KeyboardInterrupt:
        _log("\n\U0001F44B Watch mode stopped.")
        sys.exit(0)


def _make_watch_logger(verbose: bool):
    """Return a print-based logger for watch mode console output."""
    def _log(msg: str, **kwargs):
        if verbose:
            print(msg, flush=True, **kwargs)
    return _log
