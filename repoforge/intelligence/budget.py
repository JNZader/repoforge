"""
Token-budgeted context selection using PageRank scores.

Selects the most important source files for LLM context injection,
constrained by a token budget. Uses PageRank scores for prioritization
and optionally AST summaries for cheaper representation.

Algorithm:
  1. Always include entry points (main.go, index.ts, cli.py) — cap each at 300 tokens
  2. Sort remaining files by PageRank score
  3. For each file (highest rank first):
     - If tree-sitter available: include AST summary (signatures only) — cheaper
     - If not: include first N lines of source
     - Stop when budget exhausted
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..graph import CodeGraph
    from .ast_extractor import ASTSymbol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ContextItem:
    """A source file or AST summary selected for LLM context injection."""

    file_path: str
    """Relative file path."""

    content: str
    """Source code or AST summary text."""

    token_estimate: int
    """Rough token count (~4 chars per token)."""

    rank_score: float
    """PageRank score of this file."""

    reason: str
    """Why selected: 'entry_point', 'highest_ranked', 'most_exports'."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CHARS_PER_TOKEN = 4
_ENTRY_POINT_CAP = 300  # max tokens per entry point
_ENTRY_POINT_NAMES = {
    "main.go", "main.py", "app.py", "server.py", "index.ts", "index.js",
    "main.rs", "Main.java", "main.ts", "main.js", "cli.py", "cli.go",
    "manage.py", "wsgi.py", "asgi.py",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def select_context(
    graph: "CodeGraph",
    ranks: dict[str, float],
    root_dir: str,
    budget_tokens: int = 4000,
    ast_symbols: dict[str, list["ASTSymbol"]] | None = None,
) -> list[ContextItem]:
    """Select the most important files for LLM context within a token budget.

    Args:
        graph: Pre-built CodeGraph with module nodes.
        ranks: PageRank scores from ranker.pagerank().
        root_dir: Absolute path to the project root.
        budget_tokens: Maximum total token budget (default 4000).
        ast_symbols: Optional pre-extracted AST symbols per file.
            If provided and a file has symbols, uses a compressed
            signatures-only representation (much cheaper in tokens).

    Returns:
        List of ContextItem ordered by selection priority.
        Never exceeds the token budget.
    """
    if budget_tokens <= 0:
        return []

    root = Path(root_dir).resolve()
    module_nodes = [n for n in graph.nodes if n.node_type == "module"]

    if not module_nodes:
        return []

    # Identify entry points
    entry_ids: set[str] = set()
    for n in module_nodes:
        name = Path(n.id).name
        parts = Path(n.id).parts
        if name in _ENTRY_POINT_NAMES:
            entry_ids.add(n.id)
        elif len(parts) >= 2 and parts[0] == "cmd":
            entry_ids.add(n.id)

    # Sort non-entry files by PageRank score descending
    other_ids = sorted(
        [n.id for n in module_nodes if n.id not in entry_ids],
        key=lambda nid: ranks.get(nid, 0),
        reverse=True,
    )

    items: list[ContextItem] = []
    remaining = budget_tokens

    # Phase 1: Entry points (always included first, capped)
    for file_id in sorted(entry_ids):
        if remaining <= 0:
            break
        item = _build_item(
            root, file_id, ranks, ast_symbols,
            reason="entry_point",
            max_tokens=min(_ENTRY_POINT_CAP, remaining),
        )
        if item and item.token_estimate <= remaining:
            items.append(item)
            remaining -= item.token_estimate

    # Phase 2: Ranked files (highest PageRank first)
    for file_id in other_ids:
        if remaining <= 0:
            break
        item = _build_item(
            root, file_id, ranks, ast_symbols,
            reason="highest_ranked",
            max_tokens=remaining,
        )
        if item and item.token_estimate <= remaining:
            items.append(item)
            remaining -= item.token_estimate

    return items


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_item(
    root: Path,
    file_id: str,
    ranks: dict[str, float],
    ast_symbols: dict[str, list["ASTSymbol"]] | None,
    reason: str,
    max_tokens: int,
) -> ContextItem | None:
    """Build a ContextItem for a file, using AST summary or raw source.

    Returns None if the file cannot be read or is empty.
    """
    # Try AST summary first (cheaper representation)
    if ast_symbols and file_id in ast_symbols:
        symbols = ast_symbols[file_id]
        if symbols:
            summary = _format_ast_summary(symbols)
            tokens = _estimate_tokens(summary)
            if tokens <= max_tokens:
                return ContextItem(
                    file_path=file_id,
                    content=summary,
                    token_estimate=tokens,
                    rank_score=ranks.get(file_id, 0),
                    reason=reason,
                )

    # Fall back to raw source (truncated to budget)
    content = _read_file(root, file_id)
    if not content:
        return None

    tokens = _estimate_tokens(content)
    if tokens > max_tokens:
        # Truncate to fit budget
        char_limit = max_tokens * _CHARS_PER_TOKEN
        content = content[:char_limit]
        tokens = max_tokens

    return ContextItem(
        file_path=file_id,
        content=content,
        token_estimate=tokens,
        rank_score=ranks.get(file_id, 0),
        reason=reason,
    )


def _format_ast_summary(symbols: list["ASTSymbol"]) -> str:
    """Format AST symbols as a signatures-only summary."""
    lines: list[str] = []
    for sym in symbols:
        lines.append(sym.signature)
    return "\n".join(lines)


def _read_file(root: Path, relative_path: str) -> str:
    """Read file content, returning empty string on failure."""
    try:
        full_path = root / relative_path
        if not full_path.is_file():
            return ""
        return full_path.read_text(errors="replace")
    except OSError:
        return ""


def _estimate_tokens(content: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return max(1, len(content) // _CHARS_PER_TOKEN)
