"""Edge provenance — label relationships in call graphs and dependency
diagrams with confidence levels: EXTRACTED, INFERRED, AMBIGUOUS.

Extracted = derived from explicit code (import, function call, type reference)
Inferred  = derived from heuristics (naming patterns, co-location, shared types)
Ambiguous = multiple interpretations possible (dynamic dispatch, reflection)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Provenance(str, Enum):
    """Confidence level for a relationship between code entities."""
    EXTRACTED = "extracted"   # Directly observable in source
    INFERRED = "inferred"     # Heuristically determined
    AMBIGUOUS = "ambiguous"   # Multiple interpretations possible


@dataclass(frozen=True)
class LabeledEdge:
    """A relationship between two entities with provenance metadata."""
    source: str
    target: str
    relation: str  # e.g. "imports", "calls", "extends", "uses"
    provenance: Provenance
    evidence: str = ""  # e.g. "import X from './Y'" or "co-located in same dir"
    weight: float = 1.0  # 0.0-1.0, higher = more confident


def classify_import_edge(source: str, target: str, is_dynamic: bool = False) -> LabeledEdge:
    """Classify an import relationship."""
    if is_dynamic:
        return LabeledEdge(
            source=source, target=target, relation="imports",
            provenance=Provenance.AMBIGUOUS,
            evidence="dynamic import — target resolved at runtime",
            weight=0.5,
        )
    return LabeledEdge(
        source=source, target=target, relation="imports",
        provenance=Provenance.EXTRACTED,
        evidence="static import statement",
        weight=1.0,
    )


def classify_call_edge(
    source: str, target: str, *,
    is_indirect: bool = False,
    is_reflection: bool = False,
) -> LabeledEdge:
    """Classify a function call relationship."""
    if is_reflection:
        return LabeledEdge(
            source=source, target=target, relation="calls",
            provenance=Provenance.AMBIGUOUS,
            evidence="reflection/dynamic dispatch — target uncertain",
            weight=0.3,
        )
    if is_indirect:
        return LabeledEdge(
            source=source, target=target, relation="calls",
            provenance=Provenance.INFERRED,
            evidence="indirect call via variable or callback",
            weight=0.6,
        )
    return LabeledEdge(
        source=source, target=target, relation="calls",
        provenance=Provenance.EXTRACTED,
        evidence="direct function call",
        weight=1.0,
    )


def classify_type_edge(source: str, target: str, *, is_structural: bool = False) -> LabeledEdge:
    """Classify a type relationship (extends, implements, uses)."""
    if is_structural:
        return LabeledEdge(
            source=source, target=target, relation="uses",
            provenance=Provenance.INFERRED,
            evidence="structural type match (duck typing)",
            weight=0.7,
        )
    return LabeledEdge(
        source=source, target=target, relation="extends",
        provenance=Provenance.EXTRACTED,
        evidence="explicit type inheritance or implementation",
        weight=1.0,
    )


def classify_colocation_edge(source: str, target: str, shared_dir: str) -> LabeledEdge:
    """Classify a co-location relationship (heuristic)."""
    return LabeledEdge(
        source=source, target=target, relation="co-located",
        provenance=Provenance.INFERRED,
        evidence=f"both in {shared_dir}",
        weight=0.4,
    )


@dataclass
class ProvenanceGraph:
    """A graph of labeled edges with provenance metadata."""
    edges: list[LabeledEdge] = field(default_factory=list)

    def add(self, edge: LabeledEdge) -> None:
        self.edges.append(edge)

    def filter_by_provenance(self, *provenances: Provenance) -> list[LabeledEdge]:
        prov_set = set(provenances)
        return [e for e in self.edges if e.provenance in prov_set]

    def filter_by_min_weight(self, min_weight: float) -> list[LabeledEdge]:
        return [e for e in self.edges if e.weight >= min_weight]

    def edges_from(self, source: str) -> list[LabeledEdge]:
        return [e for e in self.edges if e.source == source]

    def edges_to(self, target: str) -> list[LabeledEdge]:
        return [e for e in self.edges if e.target == target]

    def confidence_summary(self) -> dict[str, int]:
        """Return count of edges per provenance level."""
        counts: dict[str, int] = {p.value: 0 for p in Provenance}
        for e in self.edges:
            counts[e.provenance.value] += 1
        return counts

    def to_dict(self) -> list[dict[str, Any]]:
        return [
            {
                "source": e.source,
                "target": e.target,
                "relation": e.relation,
                "provenance": e.provenance.value,
                "evidence": e.evidence,
                "weight": e.weight,
            }
            for e in self.edges
        ]

    @classmethod
    def from_dict(cls, data: list[dict[str, Any]]) -> ProvenanceGraph:
        graph = cls()
        for item in data:
            graph.add(LabeledEdge(
                source=item["source"],
                target=item["target"],
                relation=item["relation"],
                provenance=Provenance(item["provenance"]),
                evidence=item.get("evidence", ""),
                weight=item.get("weight", 1.0),
            ))
        return graph
