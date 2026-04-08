"""IR type for the context bundle built by pipeline/context.py.

Unlike other IR types, ContextBundle is MUTABLE — it is built
incrementally by ``build_all_contexts()`` helper functions that
populate fields one at a time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextBundle:
    """Typed replacement for the dict returned by ``build_all_contexts()``.

    Public fields are serializable context strings consumed by prompt
    generation.  Private fields (``_``-prefixed) hold runtime objects
    that are NOT included in ``to_dict()`` output.
    """

    graph_ctx: str = ""
    short_graph_ctx: str = ""
    diagram_ctx: str = ""
    semantic_ctx: str = ""
    facts_ctx: str = ""
    api_surface_ctx: str = ""
    doc_chunks: dict = field(default_factory=dict)
    fo_context_by_chapter: dict | None = None
    dep_health_ctx: str = ""
    coverage_ctx: str = ""

    # -- internal / non-serialized --
    _graph: Any = None
    """CodeGraph instance (not owned, not serialized)."""

    _facts: list = field(default_factory=list)
    """list[FactItem] — raw facts for downstream use."""

    _all_files: list[str] = field(default_factory=list)
    """All file paths gathered from repo_map layers."""

    # -- dict-compat bridge (Phase 2 migration) --
    # Allows ``ctx["semantic_ctx"]`` and ``ctx.get("diagram_ctx", "")``
    # so downstream consumers keep working until Phase 3 migrates them.

    def get(self, key: str, default=None):
        """Allow ``ctx.get("graph_ctx")`` while consumers migrate."""
        d = self.to_dict()
        # Include private fields that consumers access
        d["_graph"] = self._graph
        d["_facts"] = self._facts
        d["_all_files"] = self._all_files
        return d.get(key, default)

    def __getitem__(self, key: str):
        d = self.to_dict()
        d["_graph"] = self._graph
        d["_facts"] = self._facts
        d["_all_files"] = self._all_files
        return d[key]

    def __setitem__(self, key: str, value):
        """Allow ``ctx["graph_ctx"] = ...`` during incremental build."""
        if key.startswith("_"):
            object.__setattr__(self, key, value)
        else:
            object.__setattr__(self, key, value)

    def __contains__(self, key: str) -> bool:
        d = self.to_dict()
        d["_graph"] = self._graph
        d["_facts"] = self._facts
        d["_all_files"] = self._all_files
        return key in d

    def to_dict(self) -> dict:
        """Serialize public fields only (skip ``_``-prefixed)."""
        return {
            "graph_ctx": self.graph_ctx,
            "short_graph_ctx": self.short_graph_ctx,
            "diagram_ctx": self.diagram_ctx,
            "semantic_ctx": self.semantic_ctx,
            "facts_ctx": self.facts_ctx,
            "api_surface_ctx": self.api_surface_ctx,
            "doc_chunks": dict(self.doc_chunks),
            "fo_context_by_chapter": (
                dict(self.fo_context_by_chapter)
                if self.fo_context_by_chapter is not None
                else None
            ),
            "dep_health_ctx": self.dep_health_ctx,
            "coverage_ctx": self.coverage_ctx,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ContextBundle:
        """Construct from a dict (e.g. deserialized from JSON).

        Private fields are NOT restored — they must be set manually
        if needed at runtime.
        """
        return cls(
            graph_ctx=d.get("graph_ctx", ""),
            short_graph_ctx=d.get("short_graph_ctx", ""),
            diagram_ctx=d.get("diagram_ctx", ""),
            semantic_ctx=d.get("semantic_ctx", ""),
            facts_ctx=d.get("facts_ctx", ""),
            api_surface_ctx=d.get("api_surface_ctx", ""),
            doc_chunks=dict(d.get("doc_chunks", {})),
            fo_context_by_chapter=d.get("fo_context_by_chapter"),
            dep_health_ctx=d.get("dep_health_ctx", ""),
            coverage_ctx=d.get("coverage_ctx", ""),
        )
