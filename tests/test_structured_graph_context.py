"""
tests/test_structured_graph_context.py — Tests for structured graph context builder.

Tests cover:
- _format_module_summary with various inputs
- build_structured_graph_context with mock CodeGraph
- build_structured_graph_context with CodeGraph + SymbolGraph enrichment
- max_modules cap works
- Integration: pipeline/context.py produces structured_graph_ctx
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repoforge.graph import CodeGraph, Edge, Node
from repoforge.graph_context import (
    _format_module_summary,
    build_structured_graph_context,
)
from repoforge.ir.context import ContextBundle

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_graph():
    """Build a small graph with known topology for testing."""
    g = CodeGraph()
    g.add_node(Node(
        id="src/a.py", name="a", node_type="module",
        file_path="src/a.py", exports=["func_a", "ClassA"],
    ))
    g.add_node(Node(
        id="src/b.py", name="b", node_type="module",
        file_path="src/b.py", exports=["func_b"],
    ))
    g.add_node(Node(
        id="src/c.py", name="c", node_type="module",
        file_path="src/c.py", exports=["func_c"],
    ))
    g.add_node(Node(
        id="src/d.py", name="d", node_type="module",
        file_path="src/d.py", exports=["func_d"],
    ))

    g.add_edge(Edge(source="src/a.py", target="src/b.py", edge_type="imports"))
    g.add_edge(Edge(source="src/b.py", target="src/c.py", edge_type="imports"))
    g.add_edge(Edge(source="src/a.py", target="src/c.py", edge_type="imports"))

    return g


@pytest.fixture
def empty_graph():
    return CodeGraph()


@pytest.fixture
def large_graph():
    """Build a graph with 40 modules to test max_modules cap."""
    g = CodeGraph()
    for i in range(40):
        g.add_node(Node(
            id=f"src/mod_{i}.py", name=f"mod_{i}", node_type="module",
            file_path=f"src/mod_{i}.py", exports=[f"func_{i}"],
        ))
    # Add edges to make some modules more connected
    for i in range(1, 40):
        g.add_edge(Edge(source=f"src/mod_{i}.py", target="src/mod_0.py", edge_type="imports"))
    return g


# ---------------------------------------------------------------------------
# _format_module_summary
# ---------------------------------------------------------------------------


class TestFormatModuleSummary:
    def test_basic_output(self):
        result = _format_module_summary(
            node_id="src/scanner.py",
            name="scanner",
            exports=["scan_repo", "detect_language"],
            dependents=["src/pipeline.py", "src/cli.py"],
            dependencies=["src/utils.py"],
            layer="core",
            num_functions=5,
            num_classes=1,
        )
        assert "## Module: scanner" in result
        assert "scan_repo" in result
        assert "detect_language" in result
        assert "pipeline" in result
        assert "cli" in result
        assert "utils" in result
        assert "core" in result
        assert "5 functions" in result
        assert "1 classes" in result

    def test_no_exports(self):
        result = _format_module_summary(
            node_id="src/empty.py", name="empty",
            exports=[], dependents=[], dependencies=[],
            layer="", num_functions=0, num_classes=0,
        )
        assert "(none detected)" in result

    def test_no_dependents(self):
        result = _format_module_summary(
            node_id="src/leaf.py", name="leaf",
            exports=["x"], dependents=[], dependencies=["src/base.py"],
            layer="utils",
        )
        assert "Called by: (none)" in result
        assert "base" in result

    def test_no_dependencies(self):
        result = _format_module_summary(
            node_id="src/root.py", name="root",
            exports=["main"], dependents=["src/cli.py"], dependencies=[],
            layer="entry",
        )
        assert "Depends on: (none)" in result

    def test_many_exports_truncated(self):
        exports = [f"func_{i}" for i in range(15)]
        result = _format_module_summary(
            node_id="src/big.py", name="big",
            exports=exports, dependents=[], dependencies=[],
            layer="core",
        )
        assert "(+5 more)" in result

    def test_many_dependents_truncated(self):
        dependents = [f"src/mod_{i}.py" for i in range(8)]
        result = _format_module_summary(
            node_id="src/hub.py", name="hub",
            exports=["x"], dependents=dependents, dependencies=[],
            layer="core",
        )
        assert "(+3 more)" in result

    def test_unknown_layer(self):
        result = _format_module_summary(
            node_id="util.py", name="util",
            exports=[], dependents=[], dependencies=[],
            layer="",
        )
        assert "Layer: unknown" in result

    def test_no_complexity_when_zero(self):
        result = _format_module_summary(
            node_id="src/x.py", name="x",
            exports=[], dependents=[], dependencies=[],
            layer="core", num_functions=0, num_classes=0,
        )
        assert "Complexity" not in result


# ---------------------------------------------------------------------------
# build_structured_graph_context — CodeGraph only
# ---------------------------------------------------------------------------


class TestBuildStructuredGraphContext:
    def test_returns_nonempty_for_graph_with_edges(self, sample_graph):
        result = build_structured_graph_context(sample_graph)
        assert result != ""
        assert "Structured Module Context" in result

    def test_includes_module_count(self, sample_graph):
        result = build_structured_graph_context(sample_graph)
        # 4 modules, should show 4/4
        assert "4/4 modules" in result

    def test_includes_module_names(self, sample_graph):
        result = build_structured_graph_context(sample_graph)
        assert "## Module: a" in result or "## Module: b" in result

    def test_includes_exports_from_node(self, sample_graph):
        result = build_structured_graph_context(sample_graph)
        assert "func_a" in result
        assert "func_b" in result

    def test_returns_empty_for_empty_graph(self, empty_graph):
        result = build_structured_graph_context(empty_graph)
        assert result == ""

    def test_returns_empty_for_no_module_nodes(self):
        g = CodeGraph()
        g.add_node(Node(id="layer:core", name="core", node_type="layer"))
        result = build_structured_graph_context(g)
        assert result == ""


# ---------------------------------------------------------------------------
# build_structured_graph_context — with SymbolGraph enrichment
# ---------------------------------------------------------------------------


class TestBuildStructuredGraphContextWithSymbolGraph:
    def test_enriches_with_symbol_graph(self, sample_graph):
        """SymbolGraph provides function/class counts and overrides exports."""
        from repoforge.symbols.extractor import Symbol
        from repoforge.symbols.graph import SymbolGraph

        sg = SymbolGraph()
        sg.add_symbol(Symbol(name="func_a", kind="function", file="src/a.py", line=1, end_line=5))
        sg.add_symbol(Symbol(name="ClassA", kind="class", file="src/a.py", line=6, end_line=20))
        sg.add_symbol(Symbol(name="helper", kind="function", file="src/a.py", line=21, end_line=30))
        sg.add_symbol(Symbol(name="func_b", kind="function", file="src/b.py", line=1, end_line=10))

        result = build_structured_graph_context(sample_graph, symbol_graph=sg)
        assert "Structured Module Context" in result
        # SymbolGraph adds ClassA and helper to exports for a.py
        assert "ClassA" in result
        assert "helper" in result
        # Should show function/class counts
        assert "2 functions" in result  # func_a, helper in a.py
        assert "1 classes" in result    # ClassA in a.py

    def test_symbol_graph_none_still_works(self, sample_graph):
        """When symbol_graph is None, falls back to Node.exports."""
        result = build_structured_graph_context(sample_graph, symbol_graph=None)
        assert result != ""
        assert "func_a" in result


# ---------------------------------------------------------------------------
# max_modules cap
# ---------------------------------------------------------------------------


class TestMaxModulesCap:
    def test_respects_max_modules(self, large_graph):
        result = build_structured_graph_context(large_graph, max_modules=5)
        # Should show 5/40
        assert "5/40 modules" in result
        # Count "## Module:" occurrences
        module_count = result.count("## Module:")
        assert module_count == 5

    def test_default_max_modules_30(self, large_graph):
        result = build_structured_graph_context(large_graph)
        assert "30/40 modules" in result
        module_count = result.count("## Module:")
        assert module_count == 30

    def test_small_graph_below_cap(self, sample_graph):
        result = build_structured_graph_context(sample_graph, max_modules=100)
        assert "4/4 modules" in result


# ---------------------------------------------------------------------------
# Integration: pipeline produces structured_graph_ctx
# ---------------------------------------------------------------------------


class TestPipelineIntegration:
    def test_context_bundle_has_field(self):
        """ContextBundle has the structured_graph_ctx field."""
        bundle = ContextBundle()
        assert hasattr(bundle, "structured_graph_ctx")
        assert bundle.structured_graph_ctx == ""

    def test_context_bundle_to_dict_includes_field(self):
        bundle = ContextBundle(structured_graph_ctx="test content")
        d = bundle.to_dict()
        assert "structured_graph_ctx" in d
        assert d["structured_graph_ctx"] == "test content"

    def test_context_bundle_from_dict_includes_field(self):
        d = {"structured_graph_ctx": "restored content"}
        bundle = ContextBundle.from_dict(d)
        assert bundle.structured_graph_ctx == "restored content"

    def test_context_bundle_get_includes_field(self):
        bundle = ContextBundle(structured_graph_ctx="via get")
        assert bundle.get("structured_graph_ctx") == "via get"

    def test_context_bundle_contains_field(self):
        bundle = ContextBundle(structured_graph_ctx="present")
        assert "structured_graph_ctx" in bundle
