"""Tests for community detection (label propagation) in graph.py."""

from repoforge.graph import (
    CodeGraph,
    Edge,
    Node,
    _infer_community_name,
    assign_communities,
    detect_communities,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(nid: str, name: str = "", layer: str = "", file_path: str = "") -> Node:
    return Node(
        id=nid,
        name=name or nid.rsplit("/", 1)[-1].replace(".py", ""),
        node_type="module",
        layer=layer,
        file_path=file_path or nid,
    )


def _make_edge(src: str, tgt: str, edge_type: str = "imports") -> Edge:
    return Edge(source=src, target=tgt, edge_type=edge_type)


# ---------------------------------------------------------------------------
# detect_communities tests (Task 4.1)
# ---------------------------------------------------------------------------

class TestDetectCommunities:
    """Test detect_communities with various graph topologies."""

    def test_two_disconnected_components(self):
        """Two separate clusters with no edges between them."""
        graph = CodeGraph()
        # Cluster A: a1 -- a2 -- a3
        for nid in ("a1.py", "a2.py", "a3.py"):
            graph.add_node(_make_node(nid))
        graph.add_edge(_make_edge("a1.py", "a2.py"))
        graph.add_edge(_make_edge("a2.py", "a3.py"))

        # Cluster B: b1 -- b2
        for nid in ("b1.py", "b2.py"):
            graph.add_node(_make_node(nid))
        graph.add_edge(_make_edge("b1.py", "b2.py"))

        communities = detect_communities(graph)

        # Should produce exactly 2 communities
        assert len(communities) == 2

        # Each community should contain the right members
        all_members = []
        for members in communities.values():
            all_members.extend(members)
        assert sorted(all_members) == ["a1.py", "a2.py", "a3.py", "b1.py", "b2.py"]

        # Members of cluster A should be in the same community
        a_communities = set()
        b_communities = set()
        for cname, members in communities.items():
            for m in members:
                if m.startswith("a"):
                    a_communities.add(cname)
                else:
                    b_communities.add(cname)
        assert len(a_communities) == 1
        assert len(b_communities) == 1
        assert a_communities != b_communities

    def test_single_cluster_fully_connected(self):
        """All nodes connected — should form a single community."""
        graph = CodeGraph()
        nodes = ["x.py", "y.py", "z.py"]
        for nid in nodes:
            graph.add_node(_make_node(nid))
        # Fully connected
        for i, src in enumerate(nodes):
            for tgt in nodes[i + 1:]:
                graph.add_edge(_make_edge(src, tgt))

        communities = detect_communities(graph)
        assert len(communities) == 1
        members = list(communities.values())[0]
        assert sorted(members) == sorted(nodes)

    def test_empty_graph(self):
        """Empty graph returns empty dict."""
        graph = CodeGraph()
        communities = detect_communities(graph)
        assert communities == {}

    def test_isolated_nodes(self):
        """Nodes with no edges — each becomes its own community."""
        graph = CodeGraph()
        for nid in ("lone1.py", "lone2.py", "lone3.py"):
            graph.add_node(_make_node(nid))

        communities = detect_communities(graph)
        # Each isolated node is its own community
        assert len(communities) == 3
        all_members = []
        for members in communities.values():
            assert len(members) == 1
            all_members.extend(members)
        assert sorted(all_members) == ["lone1.py", "lone2.py", "lone3.py"]

    def test_chain_topology(self):
        """Linear chain: a -- b -- c -- d. Should converge to single community."""
        graph = CodeGraph()
        chain = ["a.py", "b.py", "c.py", "d.py"]
        for nid in chain:
            graph.add_node(_make_node(nid))
        for i in range(len(chain) - 1):
            graph.add_edge(_make_edge(chain[i], chain[i + 1]))

        communities = detect_communities(graph)
        # Chain should converge to a single community
        assert len(communities) == 1

    def test_star_topology(self):
        """Star: center connected to all spokes. Single community."""
        graph = CodeGraph()
        center = "hub.py"
        spokes = [f"spoke{i}.py" for i in range(5)]
        graph.add_node(_make_node(center))
        for s in spokes:
            graph.add_node(_make_node(s))
            graph.add_edge(_make_edge(center, s))

        communities = detect_communities(graph)
        assert len(communities) == 1

    def test_skips_non_module_nodes(self):
        """Layer nodes should be ignored by community detection."""
        graph = CodeGraph()
        graph.add_node(Node(id="layer:core", name="core", node_type="layer"))
        graph.add_node(_make_node("mod.py"))
        graph.add_edge(Edge(source="layer:core", target="mod.py", edge_type="contains"))

        communities = detect_communities(graph)
        # Only module nodes participate
        all_ids = [nid for members in communities.values() for nid in members]
        assert "layer:core" not in all_ids
        assert "mod.py" in all_ids

    def test_depends_on_edge_type(self):
        """depends_on edges are also used for community detection."""
        graph = CodeGraph()
        for nid in ("a.py", "b.py"):
            graph.add_node(_make_node(nid))
        graph.add_edge(_make_edge("a.py", "b.py", edge_type="depends_on"))

        communities = detect_communities(graph)
        assert len(communities) == 1


# ---------------------------------------------------------------------------
# Determinism test (Task 4.2)
# ---------------------------------------------------------------------------

class TestDeterminism:
    """Same graph must always produce identical communities."""

    def test_deterministic_results(self):
        """Run detect_communities 10x and verify all results are identical."""
        graph = CodeGraph()
        # Build a non-trivial graph with multiple potential communities
        for nid in ("src/a.py", "src/b.py", "src/c.py", "lib/x.py", "lib/y.py"):
            graph.add_node(_make_node(nid))
        graph.add_edge(_make_edge("src/a.py", "src/b.py"))
        graph.add_edge(_make_edge("src/b.py", "src/c.py"))
        graph.add_edge(_make_edge("lib/x.py", "lib/y.py"))

        first_result = detect_communities(graph)
        for _ in range(9):
            result = detect_communities(graph)
            assert result == first_result, "detect_communities is non-deterministic"


# ---------------------------------------------------------------------------
# _infer_community_name tests (Task 4.3 equivalent)
# ---------------------------------------------------------------------------

class TestInferCommunityName:
    """Test the community naming heuristic."""

    def test_layer_dominant(self):
        """When majority of nodes share a layer, use that layer name."""
        nodes = [
            _make_node("a.py", layer="core"),
            _make_node("b.py", layer="core"),
            _make_node("c.py", layer="api"),
        ]
        name = _infer_community_name(nodes)
        assert name == "core"

    def test_common_directory_prefix(self):
        """When nodes share a directory prefix, use it."""
        nodes = [
            _make_node("src/auth/login.py", file_path="src/auth/login.py"),
            _make_node("src/auth/logout.py", file_path="src/auth/logout.py"),
            _make_node("src/auth/middleware.py", file_path="src/auth/middleware.py"),
        ]
        name = _infer_community_name(nodes)
        assert name == "src/auth"

    def test_fallback_to_empty(self):
        """When no pattern found, return empty string."""
        nodes = [
            _make_node("x.py", name="x"),
            _make_node("y.py", name="y"),
        ]
        name = _infer_community_name(nodes)
        assert name == ""

    def test_empty_list(self):
        """Empty node list returns empty string."""
        assert _infer_community_name([]) == ""


# ---------------------------------------------------------------------------
# assign_communities tests
# ---------------------------------------------------------------------------

class TestAssignCommunities:
    """Test that assign_communities sets node.community fields."""

    def test_assigns_fields(self):
        """Nodes should have community field set after assignment."""
        graph = CodeGraph()
        graph.add_node(_make_node("a.py"))
        graph.add_node(_make_node("b.py"))
        graph.add_edge(_make_edge("a.py", "b.py"))

        assign_communities(graph)

        for node in graph.nodes:
            if node.node_type == "module":
                assert node.community != "", f"Node {node.id} has no community"

    def test_assigns_with_precomputed(self):
        """When pre-computed communities are passed, use them."""
        graph = CodeGraph()
        graph.add_node(_make_node("a.py"))
        graph.add_node(_make_node("b.py"))

        communities = {"my-group": ["a.py", "b.py"]}
        assign_communities(graph, communities)

        assert graph.get_node("a.py").community == "my-group"
        assert graph.get_node("b.py").community == "my-group"
