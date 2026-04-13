"""
cross_repo.py — Cross-repo code graph registry.

Register multiple repos, build/cache lightweight structural graphs for each,
and enable cross-repo search. Find how different projects implement similar
patterns.

Registry stored at: ~/.repoforge/registry.json

Entry points:
  - registry_add(repo_path) → adds repo to the registry
  - registry_remove(repo_path) → removes repo from the registry
  - registry_list() → list all registered repos
  - registry_search(query, top_k) → search across all registered repos
  - registry_build(repo_path) → force rebuild graph for a repo
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .graph import CodeGraph, Edge, Node, build_graph_v2
from .incremental_graph import build_graph_incremental
from .semantic_search import (
    BehaviorIndex,
    BehaviorMatch,
    build_behavior_index,
)

logger = logging.getLogger(__name__)

REGISTRY_DIR = Path.home() / ".repoforge"
REGISTRY_FILE = REGISTRY_DIR / "registry.json"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RepoEntry:
    """A registered repository in the cross-repo registry."""

    path: str
    """Absolute path to the repository root."""

    name: str
    """Short display name (derived from directory name)."""

    registered_at: str
    """ISO 8601 timestamp of when the repo was registered."""

    last_built: str | None = None
    """ISO 8601 timestamp of last graph build, or None."""

    node_count: int = 0
    edge_count: int = 0
    file_count: int = 0

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "name": self.name,
            "registered_at": self.registered_at,
            "last_built": self.last_built,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "file_count": self.file_count,
        }


@dataclass
class CrossRepoMatch:
    """A search result from cross-repo search."""

    repo_name: str
    repo_path: str
    function_name: str
    file_path: str
    line: int
    score: float
    signature: str
    complexity: str
    behavior: str

    def to_dict(self) -> dict:
        return {
            "repo": self.repo_name,
            "repo_path": self.repo_path,
            "function": self.function_name,
            "file": self.file_path,
            "line": self.line,
            "score": round(self.score, 4),
            "signature": self.signature,
            "complexity": self.complexity,
            "behavior": self.behavior,
        }


# ---------------------------------------------------------------------------
# Registry I/O
# ---------------------------------------------------------------------------


def _ensure_registry_dir() -> None:
    """Create ~/.repoforge/ if it doesn't exist."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


def _load_registry() -> dict[str, dict]:
    """Load registry from disk. Returns {abs_path: entry_dict}."""
    if not REGISTRY_FILE.exists():
        return {}
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return data.get("repos", {})
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Corrupt registry file: %s — starting fresh", exc)
        return {}


def _save_registry(repos: dict[str, dict]) -> None:
    """Save registry to disk."""
    _ensure_registry_dir()
    data = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "repos": repos,
    }
    REGISTRY_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _entry_from_dict(d: dict) -> RepoEntry:
    """Reconstruct RepoEntry from stored dict."""
    return RepoEntry(
        path=d["path"],
        name=d["name"],
        registered_at=d["registered_at"],
        last_built=d.get("last_built"),
        node_count=d.get("node_count", 0),
        edge_count=d.get("edge_count", 0),
        file_count=d.get("file_count", 0),
    )


# ---------------------------------------------------------------------------
# Registry operations
# ---------------------------------------------------------------------------


def registry_add(repo_path: str) -> RepoEntry:
    """Register a repository in the cross-repo registry.

    Resolves the path to absolute, validates it exists, adds it to
    the registry, and builds the graph immediately.

    Args:
        repo_path: Path to the repository root (relative or absolute).

    Returns:
        RepoEntry for the registered repo.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If the path is already registered.
    """
    resolved = Path(repo_path).resolve()
    if not resolved.is_dir():
        msg = f"Path does not exist or is not a directory: {resolved}"
        raise FileNotFoundError(msg)

    abs_path = str(resolved)
    repos = _load_registry()

    if abs_path in repos:
        msg = f"Repository already registered: {abs_path}"
        raise ValueError(msg)

    entry = RepoEntry(
        path=abs_path,
        name=resolved.name,
        registered_at=datetime.now(timezone.utc).isoformat(),
    )

    # Build the graph immediately
    entry = _build_graph_for_entry(entry)

    repos[abs_path] = entry.to_dict()
    _save_registry(repos)

    logger.info("Registered %s (%s)", entry.name, abs_path)
    return entry


def registry_remove(repo_path: str) -> bool:
    """Remove a repository from the registry.

    Args:
        repo_path: Path to the repository (resolved to absolute).

    Returns:
        True if removed, False if not found.
    """
    resolved = str(Path(repo_path).resolve())
    repos = _load_registry()

    if resolved not in repos:
        return False

    del repos[resolved]
    _save_registry(repos)
    logger.info("Removed %s from registry", resolved)
    return True


def registry_list() -> list[RepoEntry]:
    """List all registered repositories.

    Returns:
        List of RepoEntry, sorted by name.
    """
    repos = _load_registry()
    entries = [_entry_from_dict(d) for d in repos.values()]
    entries.sort(key=lambda e: e.name.lower())
    return entries


def registry_build(repo_path: str) -> RepoEntry:
    """Force rebuild the graph for a registered repository.

    Args:
        repo_path: Path to the repository.

    Returns:
        Updated RepoEntry.

    Raises:
        KeyError: If the repo is not registered.
    """
    resolved = str(Path(repo_path).resolve())
    repos = _load_registry()

    if resolved not in repos:
        msg = f"Repository not registered: {resolved}"
        raise KeyError(msg)

    entry = _entry_from_dict(repos[resolved])
    entry = _build_graph_for_entry(entry)

    repos[resolved] = entry.to_dict()
    _save_registry(repos)
    return entry


def registry_search(
    query: str,
    *,
    top_k: int = 10,
    depth: int = 3,
    repos: list[str] | None = None,
) -> list[CrossRepoMatch]:
    """Search across all registered repositories by behavior.

    Builds a behavior index for each repo (using incremental caching),
    searches each index, then merges and ranks results globally.

    Args:
        query: Natural language behavior description.
        top_k: Maximum total results across all repos.
        depth: Analysis depth for behavior extraction (1-5).
        repos: Optional list of repo paths to restrict search to.

    Returns:
        List of CrossRepoMatch, sorted by score descending.
    """
    all_entries = registry_list()

    if repos:
        resolved_filter = {str(Path(r).resolve()) for r in repos}
        all_entries = [e for e in all_entries if e.path in resolved_filter]

    if not all_entries:
        return []

    all_matches: list[CrossRepoMatch] = []

    for entry in all_entries:
        repo_root = Path(entry.path)
        if not repo_root.is_dir():
            logger.warning("Skipping missing repo: %s", entry.path)
            continue

        try:
            index = build_behavior_index(entry.path, depth=depth)
            results = index.search(query, top_k=top_k)

            for match in results:
                all_matches.append(
                    CrossRepoMatch(
                        repo_name=entry.name,
                        repo_path=entry.path,
                        function_name=match.function_name,
                        file_path=match.file_path,
                        line=match.line,
                        score=match.score,
                        signature=match.descriptor.signature,
                        complexity=match.descriptor.complexity_rating,
                        behavior=match.descriptor.full_text[:200],
                    )
                )
        except Exception:
            logger.exception("Error searching repo %s", entry.name)

    # Sort by score descending, take top_k
    all_matches.sort(key=lambda m: m.score, reverse=True)
    return all_matches[:top_k]


# ---------------------------------------------------------------------------
# Graph building helper
# ---------------------------------------------------------------------------


def _build_graph_for_entry(entry: RepoEntry) -> RepoEntry:
    """Build the graph for a repo and update entry stats."""
    start = time.monotonic()

    graph, stats = build_graph_incremental(entry.path)

    elapsed = time.monotonic() - start

    entry.last_built = datetime.now(timezone.utc).isoformat()
    entry.node_count = len(graph.nodes)
    entry.edge_count = len(graph.edges)
    entry.file_count = stats.get("total_files", 0)

    logger.info(
        "Built graph for %s: %d nodes, %d edges in %.1fs",
        entry.name,
        entry.node_count,
        entry.edge_count,
        elapsed,
    )
    return entry


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_registry_list(entries: list[RepoEntry]) -> str:
    """Format registry list as human-readable table."""
    if not entries:
        return "No repositories registered.\nUse `repoforge registry add <path>` to register one.\n"

    lines: list[str] = []
    lines.append(f"{'Name':<25} {'Nodes':>6} {'Edges':>6} {'Files':>6}  Path")
    lines.append("-" * 80)

    for e in entries:
        built = "yes" if e.last_built else "no"
        lines.append(
            f"{e.name:<25} {e.node_count:>6} {e.edge_count:>6} {e.file_count:>6}  {e.path}"
        )

    lines.append("")
    lines.append(f"Total: {len(entries)} repositories")
    return "\n".join(lines)


def format_cross_repo_results(results: list[CrossRepoMatch]) -> str:
    """Format cross-repo search results as human-readable markdown."""
    if not results:
        return "No matching functions found across registered repositories.\n"

    lines: list[str] = []
    lines.append(f"## Cross-Repo Search Results ({len(results)} matches)")
    lines.append("")

    current_repo = ""
    for i, match in enumerate(results, 1):
        if match.repo_name != current_repo:
            current_repo = match.repo_name
            lines.append(f"### {current_repo} (`{match.repo_path}`)")
            lines.append("")

        lines.append(
            f"{i}. **`{match.function_name}`** (score: {match.score:.3f})"
        )
        lines.append(f"   File: `{match.file_path}:L{match.line}`")
        lines.append(f"   Signature: `{match.signature}`")
        lines.append(f"   Complexity: {match.complexity}")
        lines.append("")

    return "\n".join(lines)


def cross_repo_results_to_json(results: list[CrossRepoMatch]) -> str:
    """Serialize cross-repo search results to JSON."""
    data = {
        "count": len(results),
        "results": [m.to_dict() for m in results],
    }
    return json.dumps(data, indent=2) + "\n"
