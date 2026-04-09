"""
bm25.py — Pure Python BM25 implementation for keyword search.

No external dependencies beyond the standard library. Provides BM25
scoring with tf-idf and length normalization for lexical search
as a fallback or complement to FAISS semantic search.
"""

from __future__ import annotations

import json
import logging
import math
import re
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .types import SearchResult

logger = logging.getLogger(__name__)

# BM25 hyperparameters — standard values from literature
_DEFAULT_K1 = 1.5
_DEFAULT_B = 0.75

# Persistence file name
_BM25_FILE = "bm25_index.json"

# Simple punctuation removal table
_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")


def _tokenize(text: str) -> list[str]:
    """Tokenize text: lowercase, strip punctuation, split on whitespace.

    This is intentionally simple — no stemming, no stop-word removal.
    Good enough for code-oriented search where identifiers matter.
    """
    cleaned = _PUNCT_RE.sub(" ", text.lower())
    return cleaned.split()


@dataclass
class BM25Index:
    """Pure Python BM25 keyword search index.

    Implements Okapi BM25 scoring with configurable k1 and b parameters.
    Stores documents in memory; serializes to JSON for persistence.

    Attributes:
        k1: Term frequency saturation parameter (default 1.5).
        b: Length normalization parameter (default 0.75).
    """

    k1: float = _DEFAULT_K1
    b: float = _DEFAULT_B

    # Internal state
    _ids: list[str] = field(default_factory=list, repr=False)
    _types: list[str] = field(default_factory=list, repr=False)
    _texts: list[str] = field(default_factory=list, repr=False)
    _doc_tokens: list[list[str]] = field(default_factory=list, repr=False)
    _doc_lengths: list[int] = field(default_factory=list, repr=False)
    _avg_dl: float = field(default=0.0, repr=False)
    _df: dict[str, int] = field(default_factory=dict, repr=False)
    _n_docs: int = field(default=0, repr=False)

    def add(
        self,
        texts: list[str],
        ids: list[str],
        entity_types: list[str],
    ) -> int:
        """Add documents to the BM25 index.

        Args:
            texts: Searchable text representations.
            ids: Unique entity identifiers (parallel to texts).
            entity_types: Entity types ('symbol', 'module', 'node') (parallel to texts).

        Returns:
            Number of documents added.

        Raises:
            ValueError: If input lists have different lengths.
        """
        if not texts:
            return 0

        if len(texts) != len(ids) or len(texts) != len(entity_types):
            raise ValueError(
                f"Input lists must have equal length: "
                f"texts={len(texts)}, ids={len(ids)}, entity_types={len(entity_types)}"
            )

        for text, doc_id, etype in zip(texts, ids, entity_types):
            tokens = _tokenize(text)
            self._ids.append(doc_id)
            self._types.append(etype)
            self._texts.append(text)
            self._doc_tokens.append(tokens)
            self._doc_lengths.append(len(tokens))

            # Update document frequency
            seen_terms: set[str] = set()
            for token in tokens:
                if token not in seen_terms:
                    self._df[token] = self._df.get(token, 0) + 1
                    seen_terms.add(token)

        self._n_docs = len(self._ids)
        self._avg_dl = sum(self._doc_lengths) / self._n_docs if self._n_docs > 0 else 0.0

        logger.debug("Added %d documents to BM25 index (total: %d)", len(texts), self._n_docs)
        return len(texts)

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """Search the BM25 index.

        Args:
            query: Natural language search query.
            top_k: Maximum number of results to return.

        Returns:
            List of SearchResult ordered by descending BM25 score.
            Empty list if the index is empty.
        """
        if self._n_docs == 0:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores: list[tuple[int, float]] = []

        for doc_idx in range(self._n_docs):
            score = self._score_document(doc_idx, query_tokens)
            if score > 0:
                scores.append((doc_idx, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        results: list[SearchResult] = []
        for doc_idx, score in scores[:top_k]:
            results.append(
                SearchResult(
                    entity_id=self._ids[doc_idx],
                    entity_type=self._types[doc_idx],
                    text=self._texts[doc_idx],
                    score=score,
                )
            )

        return results

    def _score_document(self, doc_idx: int, query_tokens: list[str]) -> float:
        """Compute BM25 score for a single document against query tokens."""
        doc_tokens = self._doc_tokens[doc_idx]
        dl = self._doc_lengths[doc_idx]
        score = 0.0

        # Build term frequency map for this document
        tf_map: dict[str, int] = {}
        for token in doc_tokens:
            tf_map[token] = tf_map.get(token, 0) + 1

        for qt in query_tokens:
            if qt not in self._df:
                continue

            tf = tf_map.get(qt, 0)
            if tf == 0:
                continue

            df = self._df[qt]

            # IDF: log((N - df + 0.5) / (df + 0.5) + 1)
            idf = math.log((self._n_docs - df + 0.5) / (df + 0.5) + 1.0)

            # TF normalization with length normalization
            tf_norm = (tf * (self.k1 + 1)) / (
                tf + self.k1 * (1 - self.b + self.b * dl / self._avg_dl)
            )

            score += idf * tf_norm

        return score

    def save(self, path: Path) -> None:
        """Save the BM25 index to a directory as JSON.

        Args:
            path: Directory to save into (created if it doesn't exist).

        Raises:
            ValueError: If the index is empty.
        """
        if self._n_docs == 0:
            raise ValueError("Cannot save empty BM25 index")

        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        data = {
            "k1": self.k1,
            "b": self.b,
            "ids": self._ids,
            "types": self._types,
            "texts": self._texts,
            "doc_tokens": self._doc_tokens,
            "doc_lengths": self._doc_lengths,
            "avg_dl": self._avg_dl,
            "df": self._df,
            "n_docs": self._n_docs,
        }

        (path / _BM25_FILE).write_text(
            json.dumps(data, ensure_ascii=False, indent=2)
        )

        logger.info("Saved BM25 index to %s (%d documents)", path, self._n_docs)

    @classmethod
    def load(cls, path: Path) -> BM25Index:
        """Load a BM25Index from a directory.

        Args:
            path: Directory containing bm25_index.json.

        Returns:
            Loaded BM25Index ready for search() calls.

        Raises:
            FileNotFoundError: If the index file doesn't exist.
        """
        path = Path(path)
        bm25_path = path / _BM25_FILE

        if not bm25_path.exists():
            raise FileNotFoundError(f"BM25 index not found: {bm25_path}")

        data = json.loads(bm25_path.read_text())

        instance = cls(k1=data["k1"], b=data["b"])
        instance._ids = data["ids"]
        instance._types = data["types"]
        instance._texts = data["texts"]
        instance._doc_tokens = data["doc_tokens"]
        instance._doc_lengths = data["doc_lengths"]
        instance._avg_dl = data["avg_dl"]
        instance._df = data["df"]
        instance._n_docs = data["n_docs"]

        logger.info("Loaded BM25 index from %s (%d documents)", path, instance._n_docs)
        return instance

    @property
    def size(self) -> int:
        """Number of documents in the index."""
        return self._n_docs
