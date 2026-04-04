"""Tests for CodeSnippet selection in graph_context.py."""

import textwrap
from pathlib import Path

import pytest

from repoforge.graph import CodeGraph, Edge, Node
from repoforge.graph_context import (
    CodeSnippet,
    select_code_snippets,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, rel: str, content: str) -> Path:
    fp = tmp_path / rel
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(textwrap.dedent(content))
    return fp


def _make_graph(*nodes_and_edges) -> CodeGraph:
    """Build a CodeGraph from (nodes, edges) tuple."""
    nodes, edges = nodes_and_edges
    g = CodeGraph()
    for n in nodes:
        g.add_node(n)
    for e in edges:
        g.add_edge(e)
    return g


def _simple_graph() -> tuple[list[Node], list[Edge]]:
    """3 modules: main.go (entry) imports server.go, server.go imports models.go."""
    nodes = [
        Node(id="cmd/main.go", name="main", node_type="module", file_path="cmd/main.go"),
        Node(id="internal/server.go", name="server", node_type="module", file_path="internal/server.go"),
        Node(id="internal/models.go", name="models", node_type="module", file_path="internal/models.go"),
        Node(id="internal/utils.go", name="utils", node_type="module", file_path="internal/utils.go"),
    ]
    edges = [
        Edge(source="cmd/main.go", target="internal/server.go", edge_type="imports"),
        Edge(source="internal/server.go", target="internal/models.go", edge_type="imports"),
        Edge(source="internal/server.go", target="internal/utils.go", edge_type="imports"),
    ]
    return nodes, edges


# ---------------------------------------------------------------------------
# CodeSnippet dataclass
# ---------------------------------------------------------------------------

class TestCodeSnippetDataclass:
    def test_creation(self):
        s = CodeSnippet(file="main.go", content="package main", token_estimate=3, reason="entry_point")
        assert s.file == "main.go"
        assert s.reason == "entry_point"

    def test_frozen(self):
        s = CodeSnippet(file="main.go", content="x", token_estimate=1, reason="entry_point")
        with pytest.raises(AttributeError):
            s.file = "other.go"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Entry point selection
# ---------------------------------------------------------------------------

class TestEntryPointSelection:
    def test_entry_points_selected_first(self, tmp_path):
        _write(tmp_path, "cmd/main.go", "package main\nfunc main() {}")
        _write(tmp_path, "internal/server.go", "package server\n// server code")
        _write(tmp_path, "internal/models.go", "package models\n// model code")
        _write(tmp_path, "internal/utils.go", "package utils\n// util code")

        graph = _make_graph(*_simple_graph())
        snippets = select_code_snippets(graph, str(tmp_path), token_budget=10000)

        assert len(snippets) >= 1
        assert snippets[0].file == "cmd/main.go"
        assert snippets[0].reason == "entry_point"

    def test_explicit_entry_points(self, tmp_path):
        _write(tmp_path, "cmd/main.go", "package main")
        _write(tmp_path, "internal/server.go", "package server")
        _write(tmp_path, "internal/models.go", "package models")
        _write(tmp_path, "internal/utils.go", "package utils")

        graph = _make_graph(*_simple_graph())
        snippets = select_code_snippets(
            graph, str(tmp_path),
            entry_points=["internal/server.go"],
            token_budget=10000,
        )

        assert snippets[0].file == "internal/server.go"
        assert snippets[0].reason == "entry_point"


# ---------------------------------------------------------------------------
# Most-connected ordering
# ---------------------------------------------------------------------------

class TestMostConnectedOrdering:
    def test_server_ranked_above_utils(self, tmp_path):
        """server.go has 3 connections (1 incoming + 2 outgoing), utils has 1."""
        _write(tmp_path, "cmd/main.go", "package main")
        _write(tmp_path, "internal/server.go", "package server\n// lots of code here")
        _write(tmp_path, "internal/models.go", "package models")
        _write(tmp_path, "internal/utils.go", "package utils")

        graph = _make_graph(*_simple_graph())
        snippets = select_code_snippets(graph, str(tmp_path), token_budget=10000)

        non_entry = [s for s in snippets if s.reason == "most_connected"]
        if len(non_entry) >= 2:
            # server.go should come before utils.go or models.go
            files = [s.file for s in non_entry]
            assert files.index("internal/server.go") < files.index("internal/utils.go")


# ---------------------------------------------------------------------------
# Token budget enforcement
# ---------------------------------------------------------------------------

class TestTokenBudget:
    def test_budget_limits_snippets(self, tmp_path):
        # main.go is ~30 chars = ~8 tokens. With budget=10 only 1 file fits.
        _write(tmp_path, "cmd/main.go", "package main\nfunc main() {}")
        _write(tmp_path, "internal/server.go", "package server\n// server with lots of code to exceed budget")
        _write(tmp_path, "internal/models.go", "package models")
        _write(tmp_path, "internal/utils.go", "package utils")

        graph = _make_graph(*_simple_graph())
        snippets = select_code_snippets(graph, str(tmp_path), token_budget=10)

        total_tokens = sum(s.token_estimate for s in snippets)
        assert total_tokens <= 10

    def test_zero_budget_returns_empty(self, tmp_path):
        _write(tmp_path, "cmd/main.go", "package main")
        _write(tmp_path, "internal/server.go", "package server")
        _write(tmp_path, "internal/models.go", "package models")
        _write(tmp_path, "internal/utils.go", "package utils")

        graph = _make_graph(*_simple_graph())
        snippets = select_code_snippets(graph, str(tmp_path), token_budget=0)
        assert snippets == []

    def test_large_budget_includes_all(self, tmp_path):
        _write(tmp_path, "cmd/main.go", "package main")
        _write(tmp_path, "internal/server.go", "package server")
        _write(tmp_path, "internal/models.go", "package models")
        _write(tmp_path, "internal/utils.go", "package utils")

        graph = _make_graph(*_simple_graph())
        snippets = select_code_snippets(graph, str(tmp_path), token_budget=100000)
        assert len(snippets) == 4


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestSnippetEdgeCases:
    def test_empty_graph(self, tmp_path):
        graph = CodeGraph()
        snippets = select_code_snippets(graph, str(tmp_path))
        assert snippets == []

    def test_missing_files_skipped(self, tmp_path):
        """Nodes in graph but files don't exist on disk — should be skipped."""
        graph = _make_graph(*_simple_graph())
        # Don't create any files
        snippets = select_code_snippets(graph, str(tmp_path), token_budget=10000)
        assert snippets == []

    def test_test_files_excluded(self, tmp_path):
        _write(tmp_path, "cmd/main.go", "package main")
        _write(tmp_path, "internal/server_test.go", "package server")

        nodes = [
            Node(id="cmd/main.go", name="main", node_type="module", file_path="cmd/main.go"),
            Node(id="internal/server_test.go", name="server_test", node_type="module", file_path="internal/server_test.go"),
        ]
        edges: list[Edge] = []
        graph = _make_graph(nodes, edges)
        snippets = select_code_snippets(graph, str(tmp_path), token_budget=10000)

        files = [s.file for s in snippets]
        assert "internal/server_test.go" not in files

    def test_token_estimate_reasonable(self, tmp_path):
        content = "x" * 400  # 400 chars -> ~100 tokens
        _write(tmp_path, "cmd/main.go", content)

        nodes = [Node(id="cmd/main.go", name="main", node_type="module", file_path="cmd/main.go")]
        graph = _make_graph(nodes, [])
        snippets = select_code_snippets(graph, str(tmp_path), token_budget=10000)

        assert len(snippets) == 1
        assert snippets[0].token_estimate == 100
