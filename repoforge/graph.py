"""
graph.py - Lightweight code knowledge graph built from scanner data.

No tree-sitter needed — uses existing RepoMap (from scan_repo()) to build
a graph of module relationships based on import/export name matching.

Outputs:
  - Mermaid flowchart diagrams (for docs / README)
  - JSON graph (D3/Cytoscape-compatible nodes + edges)
  - DOT format (for Graphviz)
  - Human-readable summary
"""

import json
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Node:
    id: str              # unique identifier (e.g., "backend/models.py")
    name: str            # display name (e.g., "models")
    node_type: str       # "module", "function", "class", "layer"
    layer: str = ""      # which layer this belongs to
    file_path: str = ""  # source file
    exports: list[str] = field(default_factory=list)


@dataclass
class Edge:
    source: str          # node id
    target: str          # node id
    edge_type: str       # "imports", "contains", "depends_on"
    weight: int = 1      # number of references


@dataclass
class CodeGraph:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    # Internal indexes (rebuilt on access)
    _node_index: dict[str, Node] = field(default_factory=dict, repr=False)
    _dirty: bool = field(default=True, repr=False)

    def _rebuild_index(self) -> None:
        if self._dirty:
            self._node_index = {n.id: n for n in self.nodes}
            self._dirty = False

    def add_node(self, node: Node) -> None:
        """Add a node. Skips if a node with the same id already exists."""
        self._rebuild_index()
        if node.id not in self._node_index:
            self.nodes.append(node)
            self._node_index[node.id] = node
            self._dirty = True

    def add_edge(self, edge: Edge) -> None:
        """Add an edge. Merges weight if an identical source→target+type already exists."""
        for existing in self.edges:
            if (existing.source == edge.source
                    and existing.target == edge.target
                    and existing.edge_type == edge.edge_type):
                existing.weight += edge.weight
                return
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[Node]:
        self._rebuild_index()
        return self._node_index.get(node_id)

    def get_dependencies(self, node_id: str) -> list[str]:
        """Get nodes that this node depends on (outgoing import edges)."""
        return [
            e.target for e in self.edges
            if e.source == node_id and e.edge_type in ("imports", "depends_on")
        ]

    def get_dependents(self, node_id: str) -> list[str]:
        """Get nodes that depend on this node (incoming import edges)."""
        return [
            e.source for e in self.edges
            if e.target == node_id and e.edge_type in ("imports", "depends_on")
        ]

    def get_blast_radius(self, node_id: str) -> list[str]:
        """Get all nodes transitively affected by changes to this node.

        Uses BFS on reverse dependency edges — if A imports B, then
        changing B affects A. Returns all transitively affected nodes
        (excluding the node itself).
        """
        affected: list[str] = []
        visited: set[str] = {node_id}
        queue: deque[str] = deque([node_id])

        while queue:
            current = queue.popleft()
            for dependent in self.get_dependents(current):
                if dependent not in visited:
                    visited.add(dependent)
                    affected.append(dependent)
                    queue.append(dependent)

        return affected

    def to_mermaid(self, max_nodes: int = 50) -> str:
        """Export as Mermaid flowchart diagram.

        Groups modules into subgraphs by layer. Limits output to
        max_nodes to keep diagrams readable.
        """
        lines = ["graph LR"]

        # Collect module nodes (skip layer nodes for cleaner diagrams)
        module_nodes = [n for n in self.nodes if n.node_type == "module"]
        if len(module_nodes) > max_nodes:
            module_nodes = module_nodes[:max_nodes]

        visible_ids = {n.id for n in module_nodes}

        # Group by layer
        by_layer: dict[str, list[Node]] = {}
        for n in module_nodes:
            layer = n.layer or "main"
            by_layer.setdefault(layer, []).append(n)

        # Render subgraphs
        for layer_name, layer_nodes in sorted(by_layer.items()):
            safe_layer = _mermaid_safe(layer_name)
            lines.append(f"    subgraph {safe_layer}")
            for n in layer_nodes:
                safe_id = _mermaid_id(n.id)
                safe_label = _mermaid_safe(n.name)
                lines.append(f"        {safe_id}[{safe_label}]")
            lines.append("    end")

        # Render edges (only imports/depends_on, skip contains)
        for e in self.edges:
            if e.edge_type == "contains":
                continue
            if e.source in visible_ids and e.target in visible_ids:
                src = _mermaid_id(e.source)
                tgt = _mermaid_id(e.target)
                lines.append(f"    {src} --> {tgt}")

        return "\n".join(lines)

    def to_json(self) -> str:
        """Export as JSON (nodes + edges format, compatible with D3/Cytoscape)."""
        data = {
            "nodes": [
                {
                    "id": n.id,
                    "name": n.name,
                    "type": n.node_type,
                    "layer": n.layer,
                    "file_path": n.file_path,
                    "exports": n.exports,
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "type": e.edge_type,
                    "weight": e.weight,
                }
                for e in self.edges
            ],
        }
        return json.dumps(data, indent=2) + "\n"

    def to_dot(self) -> str:
        """Export as DOT format (for Graphviz)."""
        lines = ["digraph CodeGraph {"]
        lines.append("    rankdir=LR;")
        lines.append('    node [shape=box, style=rounded];')
        lines.append("")

        # Group by layer using subgraph clusters
        by_layer: dict[str, list[Node]] = {}
        for n in self.nodes:
            if n.node_type == "module":
                layer = n.layer or "main"
                by_layer.setdefault(layer, []).append(n)

        for layer_name, layer_nodes in sorted(by_layer.items()):
            safe_cluster = re.sub(r"[^a-zA-Z0-9_]", "_", layer_name)
            lines.append(f"    subgraph cluster_{safe_cluster} {{")
            lines.append(f'        label="{layer_name}";')
            for n in layer_nodes:
                safe_id = _dot_id(n.id)
                lines.append(f'        {safe_id} [label="{n.name}"];')
            lines.append("    }")
            lines.append("")

        # Edges
        for e in self.edges:
            if e.edge_type == "contains":
                continue
            src = _dot_id(e.source)
            tgt = _dot_id(e.target)
            lines.append(f"    {src} -> {tgt};")

        lines.append("}")
        return "\n".join(lines)

    def summary(self) -> str:
        """Human-readable summary: node count, edge count, most connected, isolated."""
        module_nodes = [n for n in self.nodes if n.node_type == "module"]
        import_edges = [e for e in self.edges if e.edge_type in ("imports", "depends_on")]

        # Count connections per node
        connections: dict[str, int] = {}
        for n in module_nodes:
            connections[n.id] = 0
        for e in import_edges:
            connections[e.source] = connections.get(e.source, 0) + 1
            connections[e.target] = connections.get(e.target, 0) + 1

        # Most connected (top 5)
        sorted_nodes = sorted(connections.items(), key=lambda x: x[1], reverse=True)
        top = sorted_nodes[:5]

        # Isolated (no connections)
        isolated = [nid for nid, count in connections.items() if count == 0]

        lines = [
            f"Modules: {len(module_nodes)}",
            f"Dependencies: {len(import_edges)}",
            f"Layers: {len({n.layer for n in module_nodes if n.layer})}",
        ]

        if top and top[0][1] > 0:
            lines.append("")
            lines.append("Most connected:")
            for nid, count in top:
                if count > 0:
                    node = self.get_node(nid)
                    name = node.name if node else nid
                    lines.append(f"  {name} ({count} connections)")

        if isolated:
            lines.append("")
            lines.append(f"Isolated modules ({len(isolated)}):")
            for nid in isolated[:5]:
                node = self.get_node(nid)
                name = node.name if node else nid
                lines.append(f"  {name}")
            if len(isolated) > 5:
                lines.append(f"  ... and {len(isolated) - 5} more")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Graph builders
# ---------------------------------------------------------------------------

def build_graph(repo_map: dict) -> CodeGraph:
    """Build a CodeGraph from a RepoMap (output of scan_repo()).

    Strategy:
      1. Create a "layer" node for each layer
      2. Create a "module" node for each module in each layer
      3. Build an export index: {exported_name: [module_ids]}
      4. Resolve imports: for each module's imports, check the export index
      5. Create "imports" edges between modules
      6. Create "contains" edges from layers to modules
    """
    graph = CodeGraph()
    layers = repo_map.get("layers", {})

    # Phase 1: Create nodes
    export_index: dict[str, list[str]] = {}  # name → [module_id, ...]

    for layer_name, layer_data in layers.items():
        # Layer node
        graph.add_node(Node(
            id=f"layer:{layer_name}",
            name=layer_name,
            node_type="layer",
            layer=layer_name,
        ))

        for module in layer_data.get("modules", []):
            mod_path = module.get("path", "")
            mod_name = module.get("name", Path(mod_path).stem if mod_path else "unknown")
            exports = module.get("exports", [])

            mod_id = mod_path  # use relative path as unique id

            graph.add_node(Node(
                id=mod_id,
                name=mod_name,
                node_type="module",
                layer=layer_name,
                file_path=mod_path,
                exports=list(exports),
            ))

            # Contains edge: layer → module
            graph.add_edge(Edge(
                source=f"layer:{layer_name}",
                target=mod_id,
                edge_type="contains",
            ))

            # Build export index
            for export_name in exports:
                export_index.setdefault(export_name, []).append(mod_id)

    # Phase 2: Resolve imports → create dependency edges
    for layer_name, layer_data in layers.items():
        for module in layer_data.get("modules", []):
            mod_id = module.get("path", "")
            imports = module.get("imports", [])

            for imp in imports:
                _resolve_import(graph, mod_id, imp, export_index, layers)

    return graph


def build_graph_from_workspace(workspace: str) -> CodeGraph:
    """Convenience: scan_repo() + build_graph() in one call."""
    from .scanner import scan_repo
    repo_map = scan_repo(workspace)
    return build_graph(repo_map)


# ---------------------------------------------------------------------------
# Import resolution
# ---------------------------------------------------------------------------

def _resolve_import(
    graph: CodeGraph,
    source_id: str,
    import_name: str,
    export_index: dict[str, list[str]],
    layers: dict,
) -> None:
    """Try to resolve an import name to a module in the graph.

    Resolution strategies (in order):
      1. Direct export match: import name matches an exported name
      2. Module name match: import name matches a module's name or file stem
      3. Package name match: import name matches a layer/directory name

    Avoids self-references and duplicate edges.
    """
    # Strategy 1: Check if any module exports this name
    if import_name in export_index:
        for target_id in export_index[import_name]:
            if target_id != source_id:
                graph.add_edge(Edge(
                    source=source_id,
                    target=target_id,
                    edge_type="imports",
                ))
                return  # Take first match to avoid noise

    # Strategy 2: Module name match (e.g., "scanner" → "repoforge/scanner.py")
    for layer_data in layers.values():
        for module in layer_data.get("modules", []):
            mod_id = module.get("path", "")
            mod_name = module.get("name", "")
            if mod_id == source_id:
                continue
            if mod_name == import_name:
                graph.add_edge(Edge(
                    source=source_id,
                    target=mod_id,
                    edge_type="imports",
                ))
                return

    # Strategy 3: Package/directory match (e.g., "repoforge" → layer path)
    import_lower = import_name.lower()
    for layer_data in layers.values():
        layer_path = layer_data.get("path", "")
        # Check if import matches the layer's directory name
        if layer_path and Path(layer_path).name.lower() == import_lower:
            for module in layer_data.get("modules", []):
                mod_id = module.get("path", "")
                if mod_id != source_id:
                    graph.add_edge(Edge(
                        source=source_id,
                        target=mod_id,
                        edge_type="depends_on",
                    ))
                    return  # Only link to first module in the package

    # If none matched → external dependency, skip (no node in graph)


# ---------------------------------------------------------------------------
# Mermaid / DOT helpers
# ---------------------------------------------------------------------------

def _mermaid_id(raw: str) -> str:
    """Convert a path/id to a valid Mermaid node identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw)


def _mermaid_safe(text: str) -> str:
    """Escape text for use in Mermaid labels."""
    # Remove characters that break Mermaid syntax
    return re.sub(r"[\"'\[\]{}|<>]", "", text)


def _dot_id(raw: str) -> str:
    """Convert a path/id to a valid DOT node identifier."""
    return '"' + raw.replace('"', '\\"') + '"'
