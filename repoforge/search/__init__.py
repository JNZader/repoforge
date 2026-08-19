"""
search — Semantic + keyword search over codebase entities.

Supports three search modes:
  - semantic: FAISS-backed cosine similarity (requires faiss-cpu)
  - bm25: Pure Python BM25 keyword search (no external dependencies)
  - hybrid: Reciprocal Rank Fusion of semantic + BM25 (default)

Requires for semantic/hybrid: pip install repoforge-ai[search]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._availability import SEARCH_AVAILABLE as SEARCH_AVAILABLE
from .bm25 import BM25Index as BM25Index
from .prepare import (
    module_to_text,
    node_to_text,
    prepare_all,
    symbol_to_text,
)
from .types import SearchResult as SearchResult

if TYPE_CHECKING:
    from .embedder import Embedder as Embedder
    from .hybrid import HybridSearchIndex as HybridSearchIndex
    from .index import SearchIndex as SearchIndex


def __getattr__(name: str):
    """Lazy import for Embedder, SearchIndex, HybridSearchIndex."""
    if name == "Embedder":
        from .embedder import Embedder
        return Embedder
    if name == "SearchIndex":
        from .index import SearchIndex
        return SearchIndex
    if name == "HybridSearchIndex":
        from .hybrid import HybridSearchIndex
        return HybridSearchIndex
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BM25Index",
    "SEARCH_AVAILABLE",
    "Embedder",
    "HybridSearchIndex",
    "SearchIndex",
    "SearchResult",
    "module_to_text",
    "node_to_text",
    "prepare_all",
    "symbol_to_text",
]
