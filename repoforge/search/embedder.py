"""
embedder.py — Embedding generation via litellm.

Uses litellm.embedding() for vector generation. Supports batch processing
with configurable batch size, and auto-detects embedding dimension from
the first API call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import litellm

logger = logging.getLogger(__name__)

# Default embedding model — OpenAI's small model is widely available
# and cost-effective. Users can override via Embedder(model=...).
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

# Maximum texts per batch to avoid API payload limits
DEFAULT_BATCH_SIZE = 100


@dataclass
class Embedder:
    """Generate embeddings via litellm.embedding().

    Supports any provider litellm supports for embeddings:
      - OpenAI: text-embedding-3-small, text-embedding-3-large
      - Anthropic: (via litellm routing)
      - Ollama: ollama/nomic-embed-text, etc.
      - Any OpenAI-compatible endpoint

    Attributes:
        model: Embedding model identifier (litellm format).
        batch_size: Max texts per API call (default 100).
        dimension: Embedding dimension (auto-detected on first call).
    """

    model: str = DEFAULT_EMBEDDING_MODEL
    batch_size: int = DEFAULT_BATCH_SIZE
    dimension: int = 0
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    _extra_kwargs: dict = field(default_factory=dict)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Splits into batches of self.batch_size to avoid API payload limits.
        Auto-detects dimension from the first successful response.

        Args:
            texts: List of strings to embed.

        Returns:
            List of embedding vectors (list of floats), one per input text.

        Raises:
            ValueError: If texts is empty.
            Exception: Propagates litellm API errors.
        """
        if not texts:
            raise ValueError("Cannot embed empty text list")

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            batch_embeddings = self._embed_batch(batch)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text string.

        Convenience method — delegates to embed() with a single-item list.
        """
        return self.embed([text])[0]

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Call litellm.embedding() for a single batch."""
        kwargs: dict = {
            "model": self.model,
            "input": texts,
            **self._extra_kwargs,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base

        response = litellm.embedding(**kwargs)

        # Extract embedding vectors from response
        # litellm returns EmbeddingResponse with .data list
        embeddings = [item["embedding"] for item in response.data]

        # Auto-detect dimension from first response
        if self.dimension == 0 and embeddings:
            self.dimension = len(embeddings[0])
            logger.debug(
                "Auto-detected embedding dimension: %d (model: %s)",
                self.dimension,
                self.model,
            )

        return embeddings
