"""
search — Semantic search over codebase entities using FAISS + embeddings.

Converts symbols, modules, and graph nodes into searchable text,
generates embeddings via litellm, and indexes them with FAISS for
fast cosine-similarity retrieval.

Requires: pip install repoforge-ai[search]
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

from .prepare import (  # noqa: F401
    module_to_text,
    node_to_text,
    prepare_all,
    symbol_to_text,
)
from .types import SearchResult  # noqa: F401

if TYPE_CHECKING:
    from .embedder import Embedder as Embedder
    from .index import SearchIndex as SearchIndex


def __getattr__(name: str):
    """Lazy import for Embedder and SearchIndex to avoid numpy/faiss at import time."""
    if name == "Embedder":
        from .embedder import Embedder
        return Embedder
    if name == "SearchIndex":
        from .index import SearchIndex
        return SearchIndex
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "SEARCH_AVAILABLE",
    "Embedder",
    "SearchIndex",
    "SearchResult",
    "module_to_text",
    "node_to_text",
    "prepare_all",
    "symbol_to_text",
]
