"""Tests for knowledge_graph — unified graph with community detection."""

import json

from repoforge.knowledge_graph import (
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    format_communities,
)


def _build_clustered_graph() -> KnowledgeGraph:
    """Build a graph with 3 clear clusters."""
    g = KnowledgeGraph()

    # Cluster A: auth module (tightly connected)
    g.add_node(KnowledgeNode("auth/login", "login", "auth/login.ts", "function"))
    g.add_node(KnowledgeNode("auth/jwt", "jwt", "auth/jwt.ts", "function"))
    g.add_node(KnowledgeNode("auth/middleware", "middleware", "auth/middleware.ts", "function"))
    g.add_edge(KnowledgeEdge("auth/login", "auth/jwt", "calls", 1.0))
    g.add_edge(KnowledgeEdge("auth/jwt", "auth/middleware", "calls", 1.0))
    g.add_edge(KnowledgeEdge("auth/middleware", "auth/login", "calls", 0.8))

    # Cluster B: database module
    g.add_node(KnowledgeNode("db/connection", "connection", "db/connection.ts", "class"))
    g.add_node(KnowledgeNode("db/models", "models", "db/models.ts", "class"))
    g.add_node(KnowledgeNode("db/migrations", "migrations", "db/migrations.ts", "function"))
    g.add_edge(KnowledgeEdge("db/connection", "db/models", "imports", 1.0))
    g.add_edge(KnowledgeEdge("db/models", "db/migrations", "calls", 0.7))

    # Cluster C: API routes
    g.add_node(KnowledgeNode("api/users", "users", "api/users.ts", "function"))
    g.add_node(KnowledgeNode("api/posts", "posts", "api/posts.ts", "function"))
    g.add_edge(KnowledgeEdge("api/users", "api/posts", "imports", 0.5))

    # Cross-cluster edges (weaker)
    g.add_edge(KnowledgeEdge("api/users", "auth/middleware", "calls", 0.6))
    g.add_edge(KnowledgeEdge("api/users", "db/models", "imports", 0.5))

    return g


class TestKnowledgeNode:
    def test_create_node(self):
        n = KnowledgeNode("id1", "myFunc", "src/lib.ts", "function")
        assert n.id == "id1"
        assert n.name == "myFunc"
        assert n.kind == "function"
        assert n.community == -1  # unassigned

    def test_node_equality(self):
        a = KnowledgeNode("id1", "x", "f.ts", "function")
        b = KnowledgeNode("id1", "x", "f.ts", "function")
        assert a.id == b.id


class TestKnowledgeGraph:
    def test_add_and_get_node(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode("n1", "func", "f.ts", "function"))
        assert g.get_node("n1") is not None
        assert g.node_count == 1

    def test_add_duplicate_node_updates(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode("n1", "old", "f.ts", "function"))
        g.add_node(KnowledgeNode("n1", "new", "f.ts", "function"))
        assert g.get_node("n1").name == "new"
        assert g.node_count == 1

    def test_add_edge(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode("a", "a", "a.ts", "function"))
        g.add_node(KnowledgeNode("b", "b", "b.ts", "function"))
        g.add_edge(KnowledgeEdge("a", "b", "calls", 1.0))
        assert g.edge_count == 1

    def test_get_neighbors(self):
        g = _build_clustered_graph()
        neighbors = g.get_neighbors("auth/login")
        assert "auth/jwt" in neighbors
        assert "auth/middleware" in neighbors

    def test_node_degree(self):
        g = _build_clustered_graph()
        degree = g.node_degree("api/users")
        assert degree >= 2  # connected to posts, middleware, models

    def test_empty_graph(self):
        g = KnowledgeGraph()
        assert g.node_count == 0
        assert g.edge_count == 0


class TestCommunityDetection:
    def test_detects_communities(self):
        g = _build_clustered_graph()
        communities = g.detect_communities()
        assert len(communities) >= 2  # at least 2 clusters
        # All nodes should have a valid community assigned
        for node in g._nodes.values():
            assert node.community >= 0

    def test_single_node_gets_community(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode("alone", "alone", "alone.ts", "function"))
        communities = g.detect_communities()
        assert len(communities) == 1

    def test_disconnected_components_get_separate_communities(self):
        g = KnowledgeGraph()
        g.add_node(KnowledgeNode("a", "a", "a.ts", "function"))
        g.add_node(KnowledgeNode("b", "b", "b.ts", "function"))
        g.add_edge(KnowledgeEdge("a", "b", "calls", 1.0))
        g.add_node(KnowledgeNode("c", "c", "c.ts", "function"))
        g.add_node(KnowledgeNode("d", "d", "d.ts", "function"))
        g.add_edge(KnowledgeEdge("c", "d", "calls", 1.0))

        communities = g.detect_communities()
        node_a = g.get_node("a")
        node_c = g.get_node("c")
        assert node_a.community != node_c.community

    def test_get_community_returns_nodes(self):
        g = _build_clustered_graph()
        g.detect_communities()
        auth_comm = g.get_node("auth/login").community
        members = g.get_community(auth_comm)
        assert len(members) >= 2


class TestGodNodes:
    def test_finds_high_degree_nodes(self):
        g = _build_clustered_graph()
        gods = g.find_god_nodes(threshold_multiplier=1.0)
        # api/users has most cross-cluster connections
        god_ids = [n.id for n in gods]
        assert len(gods) >= 1

    def test_no_god_nodes_in_uniform_graph(self):
        g = KnowledgeGraph()
        # Ring topology — all same degree
        for i in range(5):
            g.add_node(KnowledgeNode(f"n{i}", f"n{i}", f"n{i}.ts", "function"))
        for i in range(5):
            g.add_edge(KnowledgeEdge(f"n{i}", f"n{(i+1)%5}", "calls", 1.0))

        gods = g.find_god_nodes(threshold_multiplier=2.0)
        assert len(gods) == 0

    def test_god_node_threshold(self):
        g = _build_clustered_graph()
        strict = g.find_god_nodes(threshold_multiplier=5.0)
        loose = g.find_god_nodes(threshold_multiplier=0.5)
        assert len(loose) >= len(strict)


class TestSerialization:
    def test_to_dict_roundtrip(self):
        g = _build_clustered_graph()
        g.detect_communities()
        data = g.to_dict()
        restored = KnowledgeGraph.from_dict(data)
        assert restored.node_count == g.node_count
        assert restored.edge_count == g.edge_count

    def test_json_serializable(self):
        g = _build_clustered_graph()
        json_str = json.dumps(g.to_dict())
        assert json_str


class TestFormat:
    def test_format_communities(self):
        g = _build_clustered_graph()
        g.detect_communities()
        text = format_communities(g)
        assert "Community" in text
        assert "auth" in text.lower() or "db" in text.lower() or "api" in text.lower()
