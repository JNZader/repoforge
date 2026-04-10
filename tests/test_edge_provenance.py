"""Tests for edge_provenance — relationship labeling with confidence."""

import json

import pytest

from repoforge.edge_provenance import (
    LabeledEdge,
    Provenance,
    ProvenanceGraph,
    classify_call_edge,
    classify_colocation_edge,
    classify_import_edge,
    classify_type_edge,
)

# ── Provenance enum ──


class TestProvenance:
    def test_values(self):
        assert Provenance.EXTRACTED.value == "extracted"
        assert Provenance.INFERRED.value == "inferred"
        assert Provenance.AMBIGUOUS.value == "ambiguous"

    def test_from_string(self):
        assert Provenance("extracted") == Provenance.EXTRACTED


# ── classify_import_edge ──


class TestClassifyImportEdge:
    def test_static_import_is_extracted(self):
        edge = classify_import_edge("app.ts", "utils.ts")
        assert edge.provenance == Provenance.EXTRACTED
        assert edge.weight == 1.0
        assert edge.relation == "imports"

    def test_dynamic_import_is_ambiguous(self):
        edge = classify_import_edge("app.ts", "plugin.ts", is_dynamic=True)
        assert edge.provenance == Provenance.AMBIGUOUS
        assert edge.weight == 0.5


# ── classify_call_edge ──


class TestClassifyCallEdge:
    def test_direct_call_is_extracted(self):
        edge = classify_call_edge("main.py", "helper.py")
        assert edge.provenance == Provenance.EXTRACTED
        assert edge.weight == 1.0

    def test_indirect_call_is_inferred(self):
        edge = classify_call_edge("main.py", "handler.py", is_indirect=True)
        assert edge.provenance == Provenance.INFERRED
        assert edge.weight == 0.6

    def test_reflection_call_is_ambiguous(self):
        edge = classify_call_edge("main.py", "target.py", is_reflection=True)
        assert edge.provenance == Provenance.AMBIGUOUS
        assert edge.weight == 0.3

    def test_reflection_takes_priority_over_indirect(self):
        edge = classify_call_edge("a", "b", is_indirect=True, is_reflection=True)
        assert edge.provenance == Provenance.AMBIGUOUS


# ── classify_type_edge ──


class TestClassifyTypeEdge:
    def test_explicit_inheritance_is_extracted(self):
        edge = classify_type_edge("Child", "Parent")
        assert edge.provenance == Provenance.EXTRACTED
        assert edge.relation == "extends"

    def test_structural_match_is_inferred(self):
        edge = classify_type_edge("Handler", "Protocol", is_structural=True)
        assert edge.provenance == Provenance.INFERRED
        assert edge.relation == "uses"
        assert edge.weight == 0.7


# ── classify_colocation_edge ──


class TestClassifyColocationEdge:
    def test_colocation_is_inferred(self):
        edge = classify_colocation_edge("a.py", "b.py", "src/utils/")
        assert edge.provenance == Provenance.INFERRED
        assert "src/utils/" in edge.evidence
        assert edge.weight == 0.4


# ── ProvenanceGraph ──


class TestProvenanceGraph:
    def _build_graph(self) -> ProvenanceGraph:
        g = ProvenanceGraph()
        g.add(classify_import_edge("app.ts", "utils.ts"))
        g.add(classify_call_edge("app.ts", "db.ts", is_indirect=True))
        g.add(classify_import_edge("app.ts", "plugin.ts", is_dynamic=True))
        g.add(classify_colocation_edge("a.py", "b.py", "src/"))
        return g

    def test_add_and_count(self):
        g = self._build_graph()
        assert len(g.edges) == 4

    def test_filter_by_provenance(self):
        g = self._build_graph()
        extracted = g.filter_by_provenance(Provenance.EXTRACTED)
        assert len(extracted) == 1
        assert all(e.provenance == Provenance.EXTRACTED for e in extracted)

    def test_filter_by_multiple_provenances(self):
        g = self._build_graph()
        result = g.filter_by_provenance(Provenance.EXTRACTED, Provenance.INFERRED)
        assert len(result) == 3

    def test_filter_by_min_weight(self):
        g = self._build_graph()
        high_conf = g.filter_by_min_weight(0.7)
        assert all(e.weight >= 0.7 for e in high_conf)

    def test_edges_from(self):
        g = self._build_graph()
        from_app = g.edges_from("app.ts")
        assert len(from_app) == 3

    def test_edges_to(self):
        g = self._build_graph()
        to_utils = g.edges_to("utils.ts")
        assert len(to_utils) == 1

    def test_confidence_summary(self):
        g = self._build_graph()
        summary = g.confidence_summary()
        assert summary["extracted"] == 1
        assert summary["inferred"] == 2
        assert summary["ambiguous"] == 1

    def test_to_dict_roundtrip(self):
        g = self._build_graph()
        data = g.to_dict()
        restored = ProvenanceGraph.from_dict(data)
        assert len(restored.edges) == len(g.edges)
        for orig, rest in zip(g.edges, restored.edges):
            assert orig.source == rest.source
            assert orig.target == rest.target
            assert orig.provenance == rest.provenance
            assert orig.weight == rest.weight

    def test_to_dict_is_json_serializable(self):
        g = self._build_graph()
        json_str = json.dumps(g.to_dict())
        assert json_str  # doesn't throw

    def test_empty_graph(self):
        g = ProvenanceGraph()
        assert g.confidence_summary() == {"extracted": 0, "inferred": 0, "ambiguous": 0}
        assert g.filter_by_provenance(Provenance.EXTRACTED) == []
