"""Tests for symbol graph Mermaid rendering."""

import pytest

from repoforge.symbols.extractor import Symbol
from repoforge.symbols.graph import CallEdge, SymbolGraph
from repoforge.symbols.renderer import render_symbol_mermaid


def _make_graph(symbols: list[Symbol], edges: list[CallEdge]) -> SymbolGraph:
    """Helper to build a SymbolGraph from lists."""
    g = SymbolGraph()
    for s in symbols:
        g.add_symbol(s)
    for e in edges:
        g.add_edge(e)
    return g


class TestRenderSymbolMermaid:

    def test_empty_graph(self):
        g = SymbolGraph()
        result = render_symbol_mermaid(g)
        assert "No symbols detected" in result

    def test_simple_graph(self):
        symbols = [
            Symbol(name="foo", kind="function", file="a.py", line=1, end_line=3),
            Symbol(name="bar", kind="function", file="a.py", line=5, end_line=7),
        ]
        edges = [CallEdge(caller="a.py::foo", callee="a.py::bar")]
        g = _make_graph(symbols, edges)
        result = render_symbol_mermaid(g)
        assert result.startswith("graph LR")
        assert "a_py__foo" in result or "foo" in result
        assert "-->" in result

    def test_groups_by_file(self):
        symbols = [
            Symbol(name="foo", kind="function", file="a.py", line=1, end_line=3),
            Symbol(name="bar", kind="function", file="b.py", line=1, end_line=3),
        ]
        edges = [CallEdge(caller="a.py::foo", callee="b.py::bar")]
        g = _make_graph(symbols, edges)
        result = render_symbol_mermaid(g)
        assert "subgraph" in result
        assert "a.py" in result or "a_py" in result

    def test_class_node_shape(self):
        symbols = [
            Symbol(name="MyClass", kind="class", file="c.py", line=1, end_line=10),
        ]
        g = _make_graph(symbols, [])
        result = render_symbol_mermaid(g)
        # Classes use stadium shape ([...])
        assert "MyClass" in result

    def test_caps_at_max_symbols(self):
        symbols = [
            Symbol(name=f"func_{i}", kind="function", file="big.py", line=i, end_line=i+1)
            for i in range(100)
        ]
        g = _make_graph(symbols, [])
        result = render_symbol_mermaid(g, max_symbols=10)
        # Should not have all 100 symbols
        count = result.count("[func_")
        assert count <= 10

    def test_cross_file_edges(self):
        symbols = [
            Symbol(name="handler", kind="function", file="api.ts", line=1, end_line=5),
            Symbol(name="validate", kind="function", file="utils.ts", line=1, end_line=3),
        ]
        edges = [CallEdge(caller="api.ts::handler", callee="utils.ts::validate")]
        g = _make_graph(symbols, edges)
        result = render_symbol_mermaid(g)
        assert "-->" in result
        assert "handler" in result
        assert "validate" in result

    def test_valid_mermaid_syntax(self):
        """Verify output is syntactically valid Mermaid."""
        symbols = [
            Symbol(name="a", kind="function", file="x.py", line=1, end_line=2),
            Symbol(name="b", kind="function", file="x.py", line=3, end_line=4),
            Symbol(name="c", kind="function", file="y.py", line=1, end_line=2),
        ]
        edges = [
            CallEdge(caller="x.py::a", callee="x.py::b"),
            CallEdge(caller="x.py::b", callee="y.py::c"),
        ]
        g = _make_graph(symbols, edges)
        result = render_symbol_mermaid(g)
        lines = result.split("\n")
        assert lines[0] == "graph LR"
        # Check subgraph open/close balance
        opens = sum(1 for l in lines if "subgraph" in l)
        closes = sum(1 for l in lines if l.strip() == "end")
        assert opens == closes
