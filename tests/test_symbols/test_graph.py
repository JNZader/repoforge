"""Tests for symbol-level call graph construction."""

import json

import pytest

from repoforge.symbols.extractor import Symbol
from repoforge.symbols.graph import (
    CONFIDENCE_ORDER,
    CallEdge,
    SymbolGraph,
    _extract_calls_in_body,
    _resolve_call,
    build_symbol_graph,
)


class TestSymbolGraph:

    def test_add_symbol(self):
        g = SymbolGraph()
        s = Symbol(name="foo", kind="function", file="a.py", line=1, end_line=3)
        g.add_symbol(s)
        assert "a.py::foo" in g.symbols

    def test_add_duplicate_symbol(self):
        g = SymbolGraph()
        s1 = Symbol(name="foo", kind="function", file="a.py", line=1, end_line=3)
        s2 = Symbol(name="foo", kind="function", file="a.py", line=5, end_line=7)
        g.add_symbol(s1)
        g.add_symbol(s2)
        # Second overwrites (same id)
        assert g.symbols["a.py::foo"].line == 5

    def test_add_edge(self):
        g = SymbolGraph()
        e = CallEdge(caller="a.py::foo", callee="a.py::bar")
        g.add_edge(e)
        assert len(g.edges) == 1

    def test_add_duplicate_edge(self):
        g = SymbolGraph()
        e1 = CallEdge(caller="a.py::foo", callee="a.py::bar")
        e2 = CallEdge(caller="a.py::foo", callee="a.py::bar")
        g.add_edge(e1)
        g.add_edge(e2)
        assert len(g.edges) == 1

    def test_get_callees(self):
        g = SymbolGraph()
        g.add_edge(CallEdge(caller="a::f", callee="a::g"))
        g.add_edge(CallEdge(caller="a::f", callee="b::h"))
        assert set(g.get_callees("a::f")) == {"a::g", "b::h"}

    def test_get_callers(self):
        g = SymbolGraph()
        g.add_edge(CallEdge(caller="a::f", callee="a::g"))
        g.add_edge(CallEdge(caller="b::h", callee="a::g"))
        assert set(g.get_callers("a::g")) == {"a::f", "b::h"}


class TestExtractCallsInBody:

    def test_simple_calls(self):
        content = "def foo():\n    bar()\n    baz(42)\n"
        sym = Symbol(name="foo", kind="function", file="a.py", line=1, end_line=3)
        calls = _extract_calls_in_body(content, sym)
        assert "bar" in calls
        assert "baz" in calls

    def test_skips_builtins(self):
        content = "def foo():\n    print('hello')\n    len(items)\n    process()\n"
        sym = Symbol(name="foo", kind="function", file="a.py", line=1, end_line=4)
        calls = _extract_calls_in_body(content, sym)
        assert "print" not in calls
        assert "len" not in calls
        assert "process" in calls

    def test_skips_recursion(self):
        content = "def foo():\n    foo()\n    bar()\n"
        sym = Symbol(name="foo", kind="function", file="a.py", line=1, end_line=3)
        calls = _extract_calls_in_body(content, sym)
        assert "foo" not in calls
        assert "bar" in calls

    def test_skips_private(self):
        content = "def foo():\n    _helper()\n    bar()\n"
        sym = Symbol(name="foo", kind="function", file="a.py", line=1, end_line=3)
        calls = _extract_calls_in_body(content, sym)
        assert "_helper" not in calls
        assert "bar" in calls


class TestBuildSymbolGraph:

    def test_intra_file_calls(self, tmp_path):
        src = tmp_path / "app.py"
        src.write_text(
            "def helper():\n"
            "    pass\n\n"
            "def main():\n"
            "    helper()\n"
        )
        graph = build_symbol_graph(str(tmp_path), ["app.py"])
        assert "app.py::helper" in graph.symbols
        assert "app.py::main" in graph.symbols
        # main calls helper
        callees = graph.get_callees("app.py::main")
        assert "app.py::helper" in callees

    def test_cross_file_calls(self, tmp_path):
        utils = tmp_path / "utils.py"
        utils.write_text("def helper():\n    pass\n")
        app = tmp_path / "app.py"
        app.write_text(
            "from utils import helper\n\n"
            "def main():\n"
            "    helper()\n"
        )
        graph = build_symbol_graph(str(tmp_path), ["utils.py", "app.py"])
        # main should call helper in utils
        callees = graph.get_callees("app.py::main")
        assert "utils.py::helper" in callees

    def test_empty_project(self, tmp_path):
        graph = build_symbol_graph(str(tmp_path), [])
        assert len(graph.symbols) == 0
        assert len(graph.edges) == 0

    def test_unsupported_files_skipped(self, tmp_path):
        (tmp_path / "data.json").write_text('{"key": "value"}')
        graph = build_symbol_graph(str(tmp_path), ["data.json"])
        assert len(graph.symbols) == 0

    def test_no_self_edges(self, tmp_path):
        src = tmp_path / "app.py"
        src.write_text(
            "def process():\n"
            "    process()\n"  # recursion
        )
        graph = build_symbol_graph(str(tmp_path), ["app.py"])
        # No self-referencing edges
        for e in graph.edges:
            assert e.caller != e.callee

    def test_multiple_files(self, tmp_path):
        (tmp_path / "a.py").write_text("def foo():\n    pass\n")
        (tmp_path / "b.py").write_text("def bar():\n    foo()\n")
        graph = build_symbol_graph(str(tmp_path), ["a.py", "b.py"])
        assert len(graph.symbols) >= 2
        callees = graph.get_callees("b.py::bar")
        assert "a.py::foo" in callees


class TestSymbolGraphToJson:

    def test_empty_graph(self):
        g = SymbolGraph()
        result = json.loads(g.to_json())
        assert result == {"symbols": [], "edges": []}

    def test_symbols_in_json(self):
        g = SymbolGraph()
        g.add_symbol(Symbol(name="foo", kind="function", file="a.py", line=1, end_line=3))
        result = json.loads(g.to_json())
        assert len(result["symbols"]) == 1
        sym = result["symbols"][0]
        assert sym["id"] == "a.py::foo"
        assert sym["name"] == "foo"
        assert sym["kind"] == "function"
        assert sym["file"] == "a.py"
        assert sym["line"] == 1
        assert sym["end_line"] == 3

    def test_edges_in_json(self):
        g = SymbolGraph()
        g.add_symbol(Symbol(name="foo", kind="function", file="a.py", line=1, end_line=3))
        g.add_symbol(Symbol(name="bar", kind="function", file="a.py", line=5, end_line=7))
        g.add_edge(CallEdge(caller="a.py::foo", callee="a.py::bar"))
        result = json.loads(g.to_json())
        assert len(result["edges"]) == 1
        edge = result["edges"][0]
        assert edge["caller"] == "a.py::foo"
        assert edge["callee"] == "a.py::bar"

    def test_json_is_valid_string(self):
        g = SymbolGraph()
        g.add_symbol(Symbol(name="x", kind="function", file="b.py", line=1, end_line=2))
        raw = g.to_json()
        assert isinstance(raw, str)
        # Should be valid JSON
        json.loads(raw)


class TestSymbolGraphSummary:

    def test_empty_graph(self):
        g = SymbolGraph()
        result = g.summary()
        assert "Functions: 0" in result
        assert "Call edges: 0" in result

    def test_counts_functions_and_classes(self):
        g = SymbolGraph()
        g.add_symbol(Symbol(name="foo", kind="function", file="a.py", line=1, end_line=3))
        g.add_symbol(Symbol(name="bar", kind="function", file="a.py", line=5, end_line=7))
        g.add_symbol(Symbol(name="Baz", kind="class", file="a.py", line=9, end_line=15))
        result = g.summary()
        assert "Functions: 2" in result
        assert "Classes: 1" in result

    def test_most_called(self):
        g = SymbolGraph()
        g.add_symbol(Symbol(name="helper", kind="function", file="a.py", line=1, end_line=3))
        g.add_symbol(Symbol(name="foo", kind="function", file="a.py", line=5, end_line=7))
        g.add_symbol(Symbol(name="bar", kind="function", file="b.py", line=1, end_line=3))
        g.add_edge(CallEdge(caller="a.py::foo", callee="a.py::helper"))
        g.add_edge(CallEdge(caller="b.py::bar", callee="a.py::helper"))
        result = g.summary()
        assert "Most called:" in result
        assert "helper (2 calls)" in result

    def test_isolated_functions(self):
        g = SymbolGraph()
        g.add_symbol(Symbol(name="lonely", kind="function", file="c.py", line=1, end_line=3))
        result = g.summary()
        assert "Isolated functions" in result
        assert "lonely" in result

    def test_file_count(self):
        g = SymbolGraph()
        g.add_symbol(Symbol(name="a", kind="function", file="x.py", line=1, end_line=2))
        g.add_symbol(Symbol(name="b", kind="function", file="y.py", line=1, end_line=2))
        result = g.summary()
        assert "Files: 2" in result


class TestCallsBlastRadiusIncompatibility:
    """Test that --blast-radius with --type calls is rejected."""

    def test_blast_radius_with_calls_exits(self):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["graph", "--type", "calls", "--blast-radius", "foo.py"])
        assert result.exit_code != 0
        assert "not supported" in result.output or "not supported" in (result.output + str(result.exception or ""))


class TestCallEdgeConfidence:
    """Phase 2 — confidence field on CallEdge."""

    def test_default_confidence_is_direct(self):
        edge = CallEdge(caller="a::f", callee="b::g")
        assert edge.confidence == "direct"

    def test_explicit_confidence(self):
        for level in ("direct", "imported", "heuristic", "linked"):
            edge = CallEdge(caller="a::f", callee="b::g", confidence=level)
            assert edge.confidence == level

    def test_confidence_preserved_in_dedup(self):
        """add_edge dedup checks caller+callee; confidence should not create duplicates."""
        g = SymbolGraph()
        g.add_edge(CallEdge(caller="a::f", callee="b::g", confidence="imported"))
        g.add_edge(CallEdge(caller="a::f", callee="b::g", confidence="direct"))
        # Dedup keeps the first one added
        assert len(g.edges) == 1
        assert g.edges[0].confidence == "imported"

    def test_json_includes_confidence(self):
        g = SymbolGraph()
        g.add_symbol(Symbol(name="f", kind="function", file="a.py", line=1, end_line=2))
        g.add_symbol(Symbol(name="g", kind="function", file="b.py", line=1, end_line=2))
        g.add_edge(CallEdge(caller="a.py::f", callee="b.py::g", confidence="imported"))
        data = json.loads(g.to_json())
        edge = data["edges"][0]
        assert edge["confidence"] == "imported"

    def test_json_default_confidence_is_direct(self):
        g = SymbolGraph()
        g.add_symbol(Symbol(name="f", kind="function", file="a.py", line=1, end_line=2))
        g.add_symbol(Symbol(name="g", kind="function", file="a.py", line=3, end_line=4))
        g.add_edge(CallEdge(caller="a.py::f", callee="a.py::g"))
        data = json.loads(g.to_json())
        assert data["edges"][0]["confidence"] == "direct"


class TestFilterEdges:
    """Phase 2 — filter_edges method on SymbolGraph."""

    @pytest.fixture()
    def graph_with_mixed_edges(self):
        g = SymbolGraph()
        for name in ("a", "b", "c", "d", "e"):
            g.add_symbol(Symbol(name=name, kind="function", file="x.py", line=1, end_line=2))
        g.edges.extend([
            CallEdge(caller="x.py::a", callee="x.py::b", confidence="direct"),
            CallEdge(caller="x.py::a", callee="x.py::c", confidence="imported"),
            CallEdge(caller="x.py::a", callee="x.py::d", confidence="linked"),
            CallEdge(caller="x.py::a", callee="x.py::e", confidence="heuristic"),
        ])
        return g

    def test_filter_heuristic_keeps_all(self, graph_with_mixed_edges):
        filtered = graph_with_mixed_edges.filter_edges(min_confidence="heuristic")
        assert len(filtered.edges) == 4

    def test_filter_linked_drops_heuristic(self, graph_with_mixed_edges):
        filtered = graph_with_mixed_edges.filter_edges(min_confidence="linked")
        confidences = {e.confidence for e in filtered.edges}
        assert "heuristic" not in confidences
        assert len(filtered.edges) == 3

    def test_filter_imported_keeps_imported_and_direct(self, graph_with_mixed_edges):
        filtered = graph_with_mixed_edges.filter_edges(min_confidence="imported")
        confidences = {e.confidence for e in filtered.edges}
        assert confidences == {"direct", "imported"}
        assert len(filtered.edges) == 2

    def test_filter_direct_keeps_only_direct(self, graph_with_mixed_edges):
        filtered = graph_with_mixed_edges.filter_edges(min_confidence="direct")
        assert len(filtered.edges) == 1
        assert filtered.edges[0].confidence == "direct"

    def test_filter_preserves_all_symbols(self, graph_with_mixed_edges):
        filtered = graph_with_mixed_edges.filter_edges(min_confidence="direct")
        assert len(filtered.symbols) == len(graph_with_mixed_edges.symbols)
        assert set(filtered.symbols.keys()) == set(graph_with_mixed_edges.symbols.keys())

    def test_filter_returns_new_graph(self, graph_with_mixed_edges):
        filtered = graph_with_mixed_edges.filter_edges(min_confidence="direct")
        assert filtered is not graph_with_mixed_edges

    def test_confidence_ordering_is_correct(self):
        assert CONFIDENCE_ORDER["direct"] > CONFIDENCE_ORDER["imported"]
        assert CONFIDENCE_ORDER["imported"] > CONFIDENCE_ORDER["linked"]
        assert CONFIDENCE_ORDER["linked"] > CONFIDENCE_ORDER["heuristic"]
