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

# FAISS availability flag — checked once at import time
SEARCH_AVAILABLE = False
try:
    import faiss  # noqa: F401
    SEARCH_AVAILABLE = True
except ImportError:
    pass

from .bm25 import BM25Index  # noqa: F401
from .prepare import (  # noqa: F401
    module_to_text,
    node_to_text,
    prepare_all,
    symbol_to_text,
)
from .types import SearchResult  # noqa: F401

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
