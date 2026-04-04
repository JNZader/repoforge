"""Tests for Wave 7: Knowledge Graph — architecture pattern detection + doc diagrams."""

import pytest

from repoforge.graph import CodeGraph, Edge, Node
from repoforge.knowledge import (
    ArchitecturePattern,
    detect_architecture_patterns,
    generate_architecture_mermaid,
)


def _layered_graph():
    """Graph with clear layered architecture: handlers → service → store."""
    g = CodeGraph()
    g.add_node(Node("handlers.py", "handlers", "module", layer="main", file_path="handlers.py",
                     exports=["HandleCreate", "HandleList"]))
    g.add_node(Node("service.py", "service", "module", layer="main", file_path="service.py",
                     exports=["CreateItem", "ListItems"]))
    g.add_node(Node("store.py", "store", "module", layer="main", file_path="store.py",
                     exports=["Insert", "Query"]))
    g.add_node(Node("models.py", "models", "module", layer="main", file_path="models.py",
                     exports=["Item", "User"]))
    g.add_edge(Edge("handlers.py", "service.py", "imports"))
    g.add_edge(Edge("service.py", "store.py", "imports"))
    g.add_edge(Edge("service.py", "models.py", "imports"))
    g.add_edge(Edge("store.py", "models.py", "imports"))
    return g


def _flat_graph():
    """Graph with no clear layers — everything imports everything."""
    g = CodeGraph()
    g.add_node(Node("a.py", "a", "module", layer="main", file_path="a.py", exports=["foo"]))
    g.add_node(Node("b.py", "b", "module", layer="main", file_path="b.py", exports=["bar"]))
    g.add_node(Node("c.py", "c", "module", layer="main", file_path="c.py", exports=["baz"]))
    g.add_edge(Edge("a.py", "b.py", "imports"))
    g.add_edge(Edge("b.py", "c.py", "imports"))
    g.add_edge(Edge("c.py", "a.py", "imports"))  # circular
    return g


def _multi_layer_graph():
    """Graph with explicit frontend/backend/shared layers."""
    g = CodeGraph()
    g.add_node(Node("frontend/app.tsx", "app", "module", layer="frontend", file_path="frontend/app.tsx"))
    g.add_node(Node("frontend/api.ts", "api", "module", layer="frontend", file_path="frontend/api.ts"))
    g.add_node(Node("backend/server.py", "server", "module", layer="backend", file_path="backend/server.py"))
    g.add_node(Node("backend/db.py", "db", "module", layer="backend", file_path="backend/db.py"))
    g.add_node(Node("shared/types.py", "types", "module", layer="shared", file_path="shared/types.py"))
    g.add_edge(Edge("frontend/app.tsx", "frontend/api.ts", "imports"))
    g.add_edge(Edge("backend/server.py", "backend/db.py", "imports"))
    g.add_edge(Edge("backend/server.py", "shared/types.py", "imports"))
    g.add_edge(Edge("frontend/api.ts", "shared/types.py", "imports"))
    return g


# ── ArchitecturePattern ──────────────────────────────────────────────────


class TestArchitecturePattern:

    def test_fields(self):
        p = ArchitecturePattern(
            name="layered", confidence=0.8,
            description="Clear layered dependency flow",
            layers=["handlers", "service", "store"],
        )
        assert p.name == "layered"
        assert p.confidence == 0.8
        assert len(p.layers) == 3


# ── detect_architecture_patterns ─────────────────────────────────────────


class TestDetectPatterns:

    def test_layered_detected(self):
        patterns = detect_architecture_patterns(_layered_graph())
        names = [p.name for p in patterns]
        assert "layered" in names

    def test_layered_has_reasonable_confidence(self):
        patterns = detect_architecture_patterns(_layered_graph())
        layered = next(p for p in patterns if p.name == "layered")
        assert layered.confidence >= 0.5

    def test_circular_detected(self):
        patterns = detect_architecture_patterns(_flat_graph())
        names = [p.name for p in patterns]
        assert "circular_deps" in names

    def test_multi_layer_detected(self):
        patterns = detect_architecture_patterns(_multi_layer_graph())
        names = [p.name for p in patterns]
        assert "multi_layer" in names

    def test_empty_graph(self):
        patterns = detect_architecture_patterns(CodeGraph())
        assert patterns == []

    def test_returns_list_of_patterns(self):
        patterns = detect_architecture_patterns(_layered_graph())
        assert isinstance(patterns, list)
        assert all(isinstance(p, ArchitecturePattern) for p in patterns)


# ── generate_architecture_mermaid ────────────────────────────────────────


class TestGenerateMermaid:

    def test_layered_produces_mermaid(self):
        mermaid = generate_architecture_mermaid(_layered_graph())
        assert "graph" in mermaid or "flowchart" in mermaid
        assert "handlers" in mermaid
        assert "store" in mermaid

    def test_multi_layer_shows_subgraphs(self):
        mermaid = generate_architecture_mermaid(_multi_layer_graph())
        assert "subgraph" in mermaid
        assert "frontend" in mermaid
        assert "backend" in mermaid

    def test_empty_graph_returns_empty(self):
        mermaid = generate_architecture_mermaid(CodeGraph())
        assert mermaid == ""

    def test_mermaid_is_valid_syntax(self):
        mermaid = generate_architecture_mermaid(_layered_graph())
        # Basic check: starts with graph/flowchart, has arrows
        assert mermaid.strip().startswith(("graph", "flowchart"))
        assert "-->" in mermaid
