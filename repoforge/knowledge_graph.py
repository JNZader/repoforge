"""Knowledge graph with community detection and god-node identification.

Builds a unified graph from codebase entities and dependencies, then:
1. Detects communities (clusters of related code) via greedy modularity
2. Identifies "god nodes" — over-connected coupling hotspots
3. Serializes to JSON for visualization

Algorithm: simplified Leiden (greedy modularity maximization)
  - Each node starts in its own community
  - For each node, try moving to each neighbor's community
  - Accept move with highest positive modularity gain
  - Repeat until convergence
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgeNode:
    """A node in the knowledge graph."""
    id: str
    name: str
    file: str
    kind: str  # function, class, method, module
    community: int = -1  # assigned by detect_communities()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeEdge:
    """An edge in the knowledge graph."""
    source: str
    target: str
    relation: str  # calls, imports, extends, uses
    weight: float = 1.0


class KnowledgeGraph:
    """A knowledge graph with community detection."""

    def __init__(self) -> None:
        self._nodes: dict[str, KnowledgeNode] = {}
        self._edges: list[KnowledgeEdge] = []
        self._adjacency: dict[str, set[str]] | None = None

    # ── Node/Edge operations ──

    def add_node(self, node: KnowledgeNode) -> None:
        self._nodes[node.id] = node
        self._adjacency = None  # invalidate cache

    def add_edge(self, edge: KnowledgeEdge) -> None:
        self._edges.append(edge)
        self._adjacency = None

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        return self._nodes.get(node_id)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    # ── Adjacency ──

    def _build_adjacency(self) -> dict[str, set[str]]:
        if self._adjacency is not None:
            return self._adjacency

        adj: dict[str, set[str]] = {nid: set() for nid in self._nodes}
        for edge in self._edges:
            if edge.source in adj:
                adj[edge.source].add(edge.target)
            if edge.target in adj:
                adj[edge.target].add(edge.source)

        self._adjacency = adj
        return adj

    def get_neighbors(self, node_id: str) -> set[str]:
        adj = self._build_adjacency()
        return adj.get(node_id, set())

    def node_degree(self, node_id: str) -> int:
        return len(self.get_neighbors(node_id))

    # ── Community detection (greedy modularity) ──

    def detect_communities(self, max_iterations: int = 50) -> dict[int, list[str]]:
        """Detect communities using greedy modularity maximization.

        Returns dict of community_id → list of node IDs.
        Also sets the `community` field on each node.
        """
        if not self._nodes:
            return {}

        adj = self._build_adjacency()
        m = len(self._edges) or 1  # total edges (avoid /0)
        node_ids = list(self._nodes.keys())

        # Initialize: each node in its own community
        community_of: dict[str, int] = {nid: i for i, nid in enumerate(node_ids)}
        degrees: dict[str, int] = {nid: len(adj.get(nid, set())) for nid in node_ids}

        # Precompute edge weights between nodes
        edge_weight: dict[tuple[str, str], float] = {}
        for edge in self._edges:
            key = (min(edge.source, edge.target), max(edge.source, edge.target))
            edge_weight[key] = edge_weight.get(key, 0) + edge.weight

        for _ in range(max_iterations):
            moved = False
            for nid in node_ids:
                current_comm = community_of[nid]
                best_comm = current_comm
                best_gain = 0.0

                # Try each neighbor's community
                neighbor_comms: set[int] = set()
                for neighbor in adj.get(nid, set()):
                    nc = community_of[neighbor]
                    if nc != current_comm:
                        neighbor_comms.add(nc)

                for target_comm in neighbor_comms:
                    gain = self._modularity_gain(
                        nid, current_comm, target_comm,
                        community_of, degrees, edge_weight, m,
                    )
                    if gain > best_gain:
                        best_gain = gain
                        best_comm = target_comm

                if best_comm != current_comm:
                    community_of[nid] = best_comm
                    moved = True

            if not moved:
                break

        # Compact community IDs
        unique_comms = sorted(set(community_of.values()))
        remap = {old: new for new, old in enumerate(unique_comms)}
        for nid in node_ids:
            community_of[nid] = remap[community_of[nid]]

        # Set on nodes
        for nid, comm in community_of.items():
            self._nodes[nid].community = comm

        # Build result
        communities: dict[int, list[str]] = {}
        for nid, comm in community_of.items():
            communities.setdefault(comm, []).append(nid)

        return communities

    def _modularity_gain(
        self,
        node_id: str,
        from_comm: int,
        to_comm: int,
        community_of: dict[str, int],
        degrees: dict[str, int],
        edge_weight: dict[tuple[str, str], float],
        m: int,
    ) -> float:
        """Calculate modularity gain of moving node to target community."""
        ki = degrees.get(node_id, 0)

        # Sum of edge weights to target community
        ki_in = 0.0
        for neighbor in self.get_neighbors(node_id):
            if community_of.get(neighbor) == to_comm:
                key = (min(node_id, neighbor), max(node_id, neighbor))
                ki_in += edge_weight.get(key, 1.0)

        # Sum of degrees in target community
        sigma_tot = sum(
            degrees.get(nid, 0)
            for nid, c in community_of.items()
            if c == to_comm
        )

        # Modularity gain formula (simplified)
        gain = ki_in / m - (sigma_tot * ki) / (2 * m * m)
        return gain

    def get_community(self, community_id: int) -> list[KnowledgeNode]:
        """Get all nodes in a community."""
        return [n for n in self._nodes.values() if n.community == community_id]

    # ── God node detection ──

    def find_god_nodes(self, threshold_multiplier: float = 2.0) -> list[KnowledgeNode]:
        """Find nodes with degree significantly above average."""
        if not self._nodes:
            return []

        degrees = {nid: self.node_degree(nid) for nid in self._nodes}
        avg_degree = sum(degrees.values()) / len(degrees) if degrees else 0

        threshold = avg_degree * threshold_multiplier
        return sorted(
            [self._nodes[nid] for nid, deg in degrees.items() if deg > threshold],
            key=lambda n: degrees.get(n.id, 0),
            reverse=True,
        )

    # ── Serialization ──

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": n.id, "name": n.name, "file": n.file,
                    "kind": n.kind, "community": n.community,
                    "metadata": n.metadata,
                }
                for n in self._nodes.values()
            ],
            "edges": [
                {
                    "source": e.source, "target": e.target,
                    "relation": e.relation, "weight": e.weight,
                }
                for e in self._edges
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeGraph:
        g = cls()
        for n in data.get("nodes", []):
            node = KnowledgeNode(
                id=n["id"], name=n["name"], file=n["file"], kind=n["kind"],
                community=n.get("community", -1),
                metadata=n.get("metadata", {}),
            )
            g.add_node(node)
        for e in data.get("edges", []):
            g.add_edge(KnowledgeEdge(
                source=e["source"], target=e["target"],
                relation=e["relation"], weight=e.get("weight", 1.0),
            ))
        return g


def format_communities(graph: KnowledgeGraph) -> str:
    """Format community detection results."""
    communities: dict[int, list[KnowledgeNode]] = {}
    for node in graph._nodes.values():
        communities.setdefault(node.community, []).append(node)

    lines = [f"## Knowledge Graph: {graph.node_count} nodes, {graph.edge_count} edges\n"]

    for comm_id in sorted(communities):
        members = communities[comm_id]
        lines.append(f"### Community {comm_id} ({len(members)} nodes)")
        for node in sorted(members, key=lambda n: n.id):
            lines.append(f"  - {node.name} ({node.kind}) — `{node.file}`")
        lines.append("")

    gods = graph.find_god_nodes()
    if gods:
        lines.append("### God Nodes (coupling hotspots)")
        for god in gods:
            degree = graph.node_degree(god.id)
            lines.append(f"  ⚠ {god.name} (degree {degree}) — `{god.file}`")

    return "\n".join(lines)
