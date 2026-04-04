"""Tests for PageRank graph scoring (repoforge.intelligence.ranker)."""

import pytest

from repoforge.graph import CodeGraph, Edge, Node
from repoforge.intelligence.ranker import pagerank, rank_files

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_graph(
    nodes: list[str],
    edges: list[tuple[str, str]],
) -> CodeGraph:
    """Build a simple module graph from node IDs and (src, tgt) edge pairs."""
    g = CodeGraph()
    for nid in nodes:
        g.add_node(Node(id=nid, name=nid, node_type="module", file_path=nid))
    for src, tgt in edges:
        g.add_edge(Edge(source=src, target=tgt, edge_type="imports"))
    return g


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPageRankBasic:
    """Core PageRank algorithm tests."""

    def test_empty_graph(self):
        """Empty graph returns empty dict."""
        g = CodeGraph()
        assert pagerank(g) == {}

    def test_single_node(self):
        """Single node graph -> score 1.0."""
        g = _make_graph(["a.py"], [])
        scores = pagerank(g)
        assert scores == {"a.py": pytest.approx(1.0)}

    def test_two_nodes_one_edge(self):
        """A -> B: B should score higher (it's imported)."""
        g = _make_graph(["a.py", "b.py"], [("a.py", "b.py")])
        scores = pagerank(g)
        assert scores["b.py"] > scores["a.py"]
        assert sum(scores.values()) == pytest.approx(1.0)

    def test_star_topology_hub_scores_highest(self):
        """Star: spokes all import hub -> hub scores highest."""
        nodes = ["hub.py", "s1.py", "s2.py", "s3.py", "s4.py"]
        edges = [
            ("s1.py", "hub.py"),
            ("s2.py", "hub.py"),
            ("s3.py", "hub.py"),
            ("s4.py", "hub.py"),
        ]
        g = _make_graph(nodes, edges)
        scores = pagerank(g)
        # Hub should have the highest score
        assert scores["hub.py"] == max(scores.values())
        # All spokes should have equal scores (symmetric)
        spoke_scores = [scores[f"s{i}.py"] for i in range(1, 5)]
        for s in spoke_scores:
            assert s == pytest.approx(spoke_scores[0], abs=1e-6)
        assert sum(scores.values()) == pytest.approx(1.0)

    def test_chain_scores_decrease(self):
        """Chain A -> B -> C: scores decrease along import chain.

        A imports B, B imports C. C is the most depended-on (transitively).
        """
        g = _make_graph(["a.py", "b.py", "c.py"], [
            ("a.py", "b.py"),
            ("b.py", "c.py"),
        ])
        scores = pagerank(g)
        # C is imported by B, B is imported by A
        # C gets rank from B, B gets rank from A
        assert scores["c.py"] > scores["b.py"]
        assert scores["b.py"] > scores["a.py"]
        assert sum(scores.values()) == pytest.approx(1.0)

    def test_cycle_equal_scores(self):
        """Cycle A -> B -> A: both should have equal scores."""
        g = _make_graph(["a.py", "b.py"], [
            ("a.py", "b.py"),
            ("b.py", "a.py"),
        ])
        scores = pagerank(g)
        assert scores["a.py"] == pytest.approx(scores["b.py"], abs=1e-6)
        assert sum(scores.values()) == pytest.approx(1.0)

    def test_disconnected_components(self):
        """Disconnected components: each gets proportional share."""
        # Component 1: a -> b
        # Component 2: c -> d
        g = _make_graph(["a.py", "b.py", "c.py", "d.py"], [
            ("a.py", "b.py"),
            ("c.py", "d.py"),
        ])
        scores = pagerank(g)
        # Symmetric structure -> b and d should be roughly equal
        assert scores["b.py"] == pytest.approx(scores["d.py"], abs=1e-4)
        assert scores["a.py"] == pytest.approx(scores["c.py"], abs=1e-4)
        assert sum(scores.values()) == pytest.approx(1.0)


class TestPageRankEdgeCases:
    """Edge cases and parameter variations."""

    def test_ignores_contains_edges(self):
        """Only imports/depends_on edges are considered."""
        g = CodeGraph()
        g.add_node(Node(id="a.py", name="a", node_type="module", file_path="a.py"))
        g.add_node(Node(id="b.py", name="b", node_type="module", file_path="b.py"))
        g.add_edge(Edge(source="a.py", target="b.py", edge_type="contains"))
        scores = pagerank(g)
        # No import edges -> uniform distribution
        assert scores["a.py"] == pytest.approx(0.5)
        assert scores["b.py"] == pytest.approx(0.5)

    def test_ignores_non_module_nodes(self):
        """Layer nodes are excluded from PageRank."""
        g = CodeGraph()
        g.add_node(Node(id="layer:core", name="core", node_type="layer"))
        g.add_node(Node(id="a.py", name="a", node_type="module", file_path="a.py"))
        g.add_edge(Edge(source="layer:core", target="a.py", edge_type="contains"))
        scores = pagerank(g)
        assert "layer:core" not in scores
        assert scores["a.py"] == pytest.approx(1.0)

    def test_depends_on_edge_type(self):
        """depends_on edges are also considered."""
        g = CodeGraph()
        g.add_node(Node(id="a.py", name="a", node_type="module", file_path="a.py"))
        g.add_node(Node(id="b.py", name="b", node_type="module", file_path="b.py"))
        g.add_edge(Edge(source="a.py", target="b.py", edge_type="depends_on"))
        scores = pagerank(g)
        assert scores["b.py"] > scores["a.py"]

    def test_custom_damping(self):
        """Custom damping factor changes distribution."""
        g = _make_graph(["a.py", "b.py"], [("a.py", "b.py")])
        scores_low = pagerank(g, damping=0.5)
        scores_high = pagerank(g, damping=0.99)
        # Higher damping -> more concentrated on imported nodes
        assert scores_high["b.py"] > scores_low["b.py"]

    def test_normalization(self):
        """Scores always sum to 1.0 regardless of graph shape."""
        g = _make_graph(
            ["a.py", "b.py", "c.py", "d.py", "e.py"],
            [
                ("a.py", "b.py"),
                ("b.py", "c.py"),
                ("c.py", "d.py"),
                ("d.py", "e.py"),
                ("e.py", "a.py"),
                ("a.py", "c.py"),
            ],
        )
        scores = pagerank(g)
        assert sum(scores.values()) == pytest.approx(1.0)


class TestRankFiles:
    """Tests for the rank_files convenience function."""

    def test_returns_sorted_descending(self):
        """rank_files returns tuples sorted by score descending."""
        g = _make_graph(["a.py", "b.py", "c.py"], [
            ("a.py", "b.py"),
            ("b.py", "c.py"),
        ])
        result = rank_files(g)
        assert len(result) == 3
        scores = [score for _, score in result]
        assert scores == sorted(scores, reverse=True)

    def test_empty_graph(self):
        """Empty graph returns empty list."""
        g = CodeGraph()
        assert rank_files(g) == []

    def test_star_hub_first(self):
        """In star topology, hub appears first."""
        nodes = ["hub.py", "s1.py", "s2.py", "s3.py"]
        edges = [
            ("s1.py", "hub.py"),
            ("s2.py", "hub.py"),
            ("s3.py", "hub.py"),
        ]
        g = _make_graph(nodes, edges)
        result = rank_files(g)
        assert result[0][0] == "hub.py"


class TestPageRankRealisticGraph:
    """Test with a realistic project-like graph structure."""

    def test_engram_like_graph_core_modules_rank_high(self):
        """Simulates an engram-like project where core modules rank highest.

        config.go is imported by 4 modules (server, main, middleware, store),
        store.go is imported by 3 (server, handlers, middleware).
        Both should rank in the top 3.
        """
        nodes = [
            "store.go",
            "server.go",
            "handlers.go",
            "main.go",
            "config.go",
            "middleware.go",
            "types.go",
        ]
        edges = [
            # server uses store, config, handlers, middleware
            ("server.go", "store.go"),
            ("server.go", "config.go"),
            ("server.go", "handlers.go"),
            ("server.go", "middleware.go"),
            # handlers use store, types
            ("handlers.go", "store.go"),
            ("handlers.go", "types.go"),
            # main uses server, config
            ("main.go", "server.go"),
            ("main.go", "config.go"),
            # middleware uses store, config
            ("middleware.go", "store.go"),
            ("middleware.go", "config.go"),
            # store uses types, config
            ("store.go", "types.go"),
            ("store.go", "config.go"),
        ]
        g = _make_graph(nodes, edges)
        result = rank_files(g)
        top_3_ids = {nid for nid, _ in result[:3]}

        # config.go (4 importers) and store.go (3 importers) must be top 3
        assert "config.go" in top_3_ids
        assert "store.go" in top_3_ids

        # main.go (imports only, never imported) should rank lowest
        assert result[-1][0] == "main.go"

        # Verify all scores sum to 1
        assert sum(s for _, s in result) == pytest.approx(1.0)
