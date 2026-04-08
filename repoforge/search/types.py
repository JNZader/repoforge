"""
types.py — Data types for the search module.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A single search result from the semantic index."""

    entity_id: str
    """Unique identifier (e.g., 'src/auth.py::authenticate' or 'src/auth.py')."""

    entity_type: str
    """Type of entity: 'symbol', 'module', or 'node'."""

    text: str
    """The searchable text that was indexed."""

    score: float
    """Cosine similarity score (higher = more relevant)."""

    metadata: dict = field(default_factory=dict)
    """Arbitrary metadata (e.g., file path, language, line number)."""
