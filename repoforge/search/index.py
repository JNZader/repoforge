"""
index.py — FAISS-backed semantic search index.

Stores embeddings in a FAISS IndexFlatIP (inner product = cosine similarity
with L2-normalized vectors). Metadata (IDs, types, texts) is stored as JSON
alongside the FAISS binary index for persistence.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .embedder import Embedder
from .types import SearchResult

logger = logging.getLogger(__name__)

# Guard FAISS + numpy imports — they're optional dependencies
try:
    import faiss
    import numpy as np

    FAISS_AVAILABLE = True
except ImportError:
    faiss = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    FAISS_AVAILABLE = False

# File names for persistence
_INDEX_FILE = "index.faiss"
_METADATA_FILE = "metadata.json"


@dataclass
class SearchIndex:
    """FAISS-backed semantic search index.

    Uses IndexFlatIP (inner product) with L2-normalized vectors,
    which is equivalent to cosine similarity search.

    Attributes:
        embedder: Embedder instance for generating vectors.
        dimension: Vector dimension (auto-detected if 0).
    """

    embedder: Embedder = field(default_factory=Embedder)
    dimension: int = 0

    # Internal state
    _index: Optional[object] = field(default=None, repr=False)
    _ids: list[str] = field(default_factory=list, repr=False)
    _types: list[str] = field(default_factory=list, repr=False)
    _texts: list[str] = field(default_factory=list, repr=False)

    def _ensure_faiss(self) -> None:
        """Raise ImportError if faiss is not available."""
        if not FAISS_AVAILABLE:
            raise ImportError(
                "faiss-cpu is required for semantic search. "
                "Install with: pip install repoforge-ai[search]"
            )

    def _ensure_index(self, dim: int) -> None:
        """Create the FAISS index if it doesn't exist yet."""
        self._ensure_faiss()
        if self._index is None:
            self.dimension = dim
            self._index = faiss.IndexFlatIP(dim)
            logger.debug("Created FAISS IndexFlatIP with dimension %d", dim)

    def add(
        self,
        texts: list[str],
        ids: list[str],
        types: list[str],
    ) -> int:
        """Embed texts and add them to the index.

        Args:
            texts: Searchable text representations.
            ids: Unique entity identifiers (parallel to texts).
            types: Entity types ('symbol', 'module', 'node') (parallel to texts).

        Returns:
            Number of vectors added.

        Raises:
            ValueError: If input lists have different lengths.
            ImportError: If faiss-cpu is not installed.
        """
        if not texts:
            return 0

        if len(texts) != len(ids) or len(texts) != len(types):
            raise ValueError(
                f"Input lists must have equal length: "
                f"texts={len(texts)}, ids={len(ids)}, types={len(types)}"
            )

        # Generate embeddings
        embeddings = self.embedder.embed(texts)
        vectors = np.array(embeddings, dtype=np.float32)

        # L2-normalize for cosine similarity via inner product
        faiss.normalize_L2(vectors)

        # Create index on first add (auto-detect dimension)
        self._ensure_index(vectors.shape[1])

        # Add to FAISS index
        self._index.add(vectors)  # type: ignore[union-attr]

        # Store metadata
        self._ids.extend(ids)
        self._types.extend(types)
        self._texts.extend(texts)

        logger.debug("Added %d vectors to index (total: %d)", len(texts), len(self._ids))
        return len(texts)

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """Search the index for the most similar entities.

        Args:
            query: Natural language search query.
            top_k: Maximum number of results to return.

        Returns:
            List of SearchResult ordered by descending similarity score.
            Empty list if the index is empty.

        Raises:
            ImportError: If faiss-cpu is not installed.
        """
        self._ensure_faiss()

        if self._index is None or len(self._ids) == 0:
            return []

        # Embed the query
        query_vec = np.array(
            self.embedder.embed_single(query), dtype=np.float32
        ).reshape(1, -1)
        faiss.normalize_L2(query_vec)

        # Search
        k = min(top_k, len(self._ids))
        scores, indices = self._index.search(query_vec, k)  # type: ignore[union-attr]

        results: list[SearchResult] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:  # FAISS returns -1 for empty slots
                continue
            results.append(
                SearchResult(
                    entity_id=self._ids[idx],
                    entity_type=self._types[idx],
                    text=self._texts[idx],
                    score=float(score),
                )
            )

        return results

    def save(self, path: Path) -> None:
        """Save the FAISS index and metadata to a directory.

        Creates two files:
          - index.faiss: Binary FAISS index
          - metadata.json: JSON with ids, types, texts, and dimension

        Args:
            path: Directory to save into (created if it doesn't exist).

        Raises:
            ImportError: If faiss-cpu is not installed.
            ValueError: If the index is empty.
        """
        self._ensure_faiss()

        if self._index is None:
            raise ValueError("Cannot save empty index")

        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        faiss.write_index(self._index, str(path / _INDEX_FILE))

        # Save metadata
        metadata = {
            "dimension": self.dimension,
            "ids": self._ids,
            "types": self._types,
            "texts": self._texts,
        }
        (path / _METADATA_FILE).write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2)
        )

        logger.info("Saved search index to %s (%d vectors)", path, len(self._ids))

    @classmethod
    def load(cls, path: Path, embedder: Optional[Embedder] = None) -> SearchIndex:
        """Load a SearchIndex from a directory.

        Args:
            path: Directory containing index.faiss and metadata.json.
            embedder: Optional Embedder instance. If None, creates a default one.

        Returns:
            Loaded SearchIndex ready for search() calls.

        Raises:
            ImportError: If faiss-cpu is not installed.
            FileNotFoundError: If the index files don't exist.
        """
        if not FAISS_AVAILABLE:
            raise ImportError(
                "faiss-cpu is required for semantic search. "
                "Install with: pip install repoforge-ai[search]"
            )

        path = Path(path)
        index_path = path / _INDEX_FILE
        meta_path = path / _METADATA_FILE

        if not index_path.exists():
            raise FileNotFoundError(f"FAISS index not found: {index_path}")
        if not meta_path.exists():
            raise FileNotFoundError(f"Metadata not found: {meta_path}")

        # Load FAISS index
        faiss_index = faiss.read_index(str(index_path))

        # Load metadata
        metadata = json.loads(meta_path.read_text())

        instance = cls(
            embedder=embedder or Embedder(),
            dimension=metadata["dimension"],
        )
        instance._index = faiss_index
        instance._ids = metadata["ids"]
        instance._types = metadata["types"]
        instance._texts = metadata["texts"]

        logger.info("Loaded search index from %s (%d vectors)", path, len(instance._ids))
        return instance

    @property
    def size(self) -> int:
        """Number of vectors in the index."""
        return len(self._ids)
