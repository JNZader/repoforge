"""
hybrid.py — Hybrid search combining BM25 (keyword) + FAISS (semantic).

Uses Reciprocal Rank Fusion (RRF) to merge results from both indexes.
Falls back gracefully: BM25-only if FAISS unavailable, semantic-only
if BM25 index is empty.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .bm25 import BM25Index
from .types import SearchResult

logger = logging.getLogger(__name__)

# RRF constant — standard value from "Reciprocal Rank Fusion outperforms
# Condorcet and individual Rank Learning Methods" (Cormack et al. 2009)
_RRF_K = 60


def _rrf_score(rank: int, k: int = _RRF_K) -> float:
    """Compute Reciprocal Rank Fusion score for a given rank (1-based)."""
    return 1.0 / (k + rank)


@dataclass
class HybridSearchIndex:
    """Hybrid search index combining BM25 keyword search + FAISS semantic search.

    Merges results using Reciprocal Rank Fusion (RRF) with configurable
    alpha weighting between semantic and keyword scores.

    Attributes:
        bm25: BM25Index for keyword search.
        semantic: Optional SearchIndex for semantic/vector search.
        embedder: Optional Embedder for the semantic index.
    """

    bm25: BM25Index = field(default_factory=BM25Index)
    semantic: Optional[object] = field(default=None, repr=False)
    _embedder: Optional[object] = field(default=None, repr=False)

    def add(
        self,
        texts: list[str],
        ids: list[str],
        types: list[str],
    ) -> int:
        """Add documents to both BM25 and semantic indexes.

        Args:
            texts: Searchable text representations.
            ids: Unique entity identifiers (parallel to texts).
            types: Entity types (parallel to texts).

        Returns:
            Number of documents added.
        """
        count = self.bm25.add(texts=texts, ids=ids, entity_types=types)

        if self.semantic is not None:
            self.semantic.add(texts=texts, ids=ids, types=types)

        return count

    def search(
        self,
        query: str,
        top_k: int = 10,
        alpha: float = 0.5,
    ) -> list[SearchResult]:
        """Search using hybrid RRF fusion of semantic + BM25.

        Args:
            query: Natural language search query.
            top_k: Maximum number of results to return.
            alpha: Weight for semantic vs BM25.
                   alpha=1.0 = pure semantic, alpha=0.0 = pure BM25.
                   Default 0.5 = equal weight.

        Returns:
            List of SearchResult ordered by descending fused score.
        """
        has_semantic = self.semantic is not None and self.semantic.size > 0
        has_bm25 = self.bm25.size > 0

        # Fallback: only one engine available
        if not has_semantic and not has_bm25:
            return []
        if not has_semantic:
            return self.bm25.search(query, top_k=top_k)
        if not has_bm25:
            return self.semantic.search(query, top_k=top_k)

        # Fetch more candidates for fusion (2x top_k from each)
        fetch_k = min(top_k * 2, max(self.bm25.size, self.semantic.size))

        semantic_results = self.semantic.search(query, top_k=fetch_k)
        bm25_results = self.bm25.search(query, top_k=fetch_k)

        # Build RRF scores
        # entity_id -> (fused_score, SearchResult from best source)
        fused: dict[str, tuple[float, SearchResult]] = {}

        # Semantic ranks (1-based)
        for rank, result in enumerate(semantic_results, start=1):
            rrf = _rrf_score(rank)
            score = alpha * rrf
            fused[result.entity_id] = (score, result)

        # BM25 ranks (1-based)
        for rank, result in enumerate(bm25_results, start=1):
            rrf = _rrf_score(rank)
            bm25_contribution = (1 - alpha) * rrf

            if result.entity_id in fused:
                existing_score, existing_result = fused[result.entity_id]
                fused[result.entity_id] = (
                    existing_score + bm25_contribution,
                    existing_result,
                )
            else:
                fused[result.entity_id] = (bm25_contribution, result)

        # Sort by fused score descending
        sorted_results = sorted(fused.values(), key=lambda x: x[0], reverse=True)

        return [
            SearchResult(
                entity_id=result.entity_id,
                entity_type=result.entity_type,
                text=result.text,
                score=score,
            )
            for score, result in sorted_results[:top_k]
        ]

    def save(self, path: Path) -> None:
        """Save both indexes to a directory.

        BM25 is always saved. FAISS is saved only if available.

        Args:
            path: Directory to save into.
        """
        path = Path(path)

        if self.bm25.size > 0:
            self.bm25.save(path)

        if self.semantic is not None and self.semantic.size > 0:
            self.semantic.save(path)

        logger.info("Saved hybrid index to %s", path)

    @classmethod
    def load(
        cls,
        path: Path,
        embedder: Optional[object] = None,
    ) -> HybridSearchIndex:
        """Load a HybridSearchIndex from a directory.

        Loads BM25 always. Loads FAISS only if available and index exists.

        Args:
            path: Directory containing index files.
            embedder: Optional Embedder for semantic search queries.

        Returns:
            Loaded HybridSearchIndex.
        """
        path = Path(path)

        # Always load BM25
        bm25 = BM25Index.load(path)

        # Try to load FAISS (optional dependency)
        semantic = None
        try:
            from .index import FAISS_AVAILABLE, SearchIndex

            if FAISS_AVAILABLE and (path / "index.faiss").exists():
                semantic = SearchIndex.load(path, embedder=embedder)
        except ImportError:
            logger.debug("FAISS not available, using BM25-only mode")

        instance = cls(bm25=bm25, semantic=semantic, _embedder=embedder)
        logger.info(
            "Loaded hybrid index from %s (BM25: %d docs, semantic: %s)",
            path,
            bm25.size,
            f"{semantic.size} vectors" if semantic else "unavailable",
        )
        return instance

    @property
    def size(self) -> int:
        """Number of documents (based on BM25, which is always available)."""
        return self.bm25.size
