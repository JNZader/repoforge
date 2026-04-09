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
import logging
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


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
    community: str = ""  # set after detect_communities()


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
                    "community": n.community,
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
# V2: Extractor-based graph builder
# ---------------------------------------------------------------------------

@dataclass
class BlastRadiusResult:
    """Enhanced blast radius result with depth tracking and test separation."""
    files: list[str] = field(default_factory=list)
    """All non-test files in the blast radius (dependents only, not changed)."""

    test_files: list[str] = field(default_factory=list)
    """Test files that depend on affected files."""

    changed_files: list[str] = field(default_factory=list)
    """The original changed file(s) that triggered the analysis."""

    depth: int = 0
    """Maximum BFS depth actually reached."""

    exceeded_cap: bool = False
    """True if the blast radius exceeded max_files cap."""


def is_test_file(file_path: str) -> bool:
    """Detect whether a file is a test file based on naming conventions.

    Patterns checked (all 6 supported languages):
    - Python: test_*.py, *_test.py
    - TypeScript/JavaScript: *.test.ts, *.spec.ts, *.test.js, *.spec.js, *.test.tsx, *.spec.tsx
    - Go: *_test.go
    - Java: *Test.java, *Tests.java
    - Rust: tests/ directory or *_test.rs
    """
    # Normalize to forward slashes
    p = file_path.replace("\\", "/")
    name = p.rsplit("/", 1)[-1] if "/" in p else p

    # Python: test_*.py, *_test.py
    if name.endswith(".py"):
        return name.startswith("test_") or name.endswith("_test.py")

    # Go: *_test.go
    if name.endswith("_test.go"):
        return True

    # TS/JS: *.test.ts, *.spec.ts, *.test.tsx, *.spec.tsx, *.test.js, etc.
    for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
        if name.endswith(f".test{ext}") or name.endswith(f".spec{ext}"):
            return True

    # Java: *Test.java, *Tests.java, *IT.java
    if name.endswith(".java"):
        stem = name[:-5]  # remove .java
        return stem.endswith("Test") or stem.endswith("Tests") or stem.endswith("IT")

    # Rust: files inside tests/ directory or *_test.rs
    if name.endswith(".rs"):
        if name.endswith("_test.rs"):
            return True
        if "/tests/" in p or p.startswith("tests/"):
            return True

    # Directory-based patterns for any language
    if "/__tests__/" in p or p.startswith("__tests__/"):
        return True

    return False


def build_graph_v2(root_dir: str, files: list[str] | None = None) -> CodeGraph:
    """Build a CodeGraph using extractor-based import/export detection.

    Unlike build_graph() which uses RepoMap data with fuzzy name matching,
    this version reads actual file content, extracts imports/exports with
    language-specific regex extractors, and resolves imports to file paths.

    Args:
        root_dir: Absolute path to the project root.
        files: Optional list of relative file paths. If None, discovers files
            using ripgrep.

    Returns:
        CodeGraph with file-level dependency edges.
    """
    from .extractors import get_extractor
    from .extractors.resolver import (
        resolve_go_import,
        resolve_import,
        resolve_python_import,
    )

    root = Path(root_dir).resolve()

    # Discover files if not provided
    if files is None:
        from .ripgrep import list_files
        discovered = list_files(root)
        files = []
        for f in discovered:
            try:
                files.append(str(f.relative_to(root)))
            except ValueError:
                pass

    available_files = set(files)
    graph = CodeGraph()

    # Phase 1: Extract imports and exports from each file, build nodes
    file_imports: dict[str, list] = {}  # file → list of ImportInfo

    # Read go.mod if present for Go resolution
    go_mod_content: str | None = None
    go_mod_path = root / "go.mod"
    if go_mod_path.exists():
        try:
            go_mod_content = go_mod_path.read_text(errors="replace")
        except OSError:
            pass

    for file_path in files:
        extractor = get_extractor(file_path)
        if not extractor:
            continue

        abs_path = root / file_path
        try:
            content = abs_path.read_text(errors="replace")
        except OSError:
            logger.debug("Failed to read %s", abs_path)
            continue

        imports = extractor.extract_imports(content)
        exports = extractor.extract_exports(content)
        is_test = is_test_file(file_path)

        # Create node
        node = Node(
            id=file_path,
            name=Path(file_path).stem,
            node_type="module",
            layer="",  # No layer detection in v2 — flat file graph
            file_path=file_path,
            exports=[e.name for e in exports],
        )
        graph.add_node(node)

        # Store imports for resolution in phase 2
        file_imports[file_path] = imports

    # Phase 2: Resolve imports to file paths and create edges
    for file_path, imports in file_imports.items():
        for imp in imports:
            resolved: str | None = None

            # Determine extractor language for dispatch
            extractor = get_extractor(file_path)
            lang = extractor.language if extractor else ""

            if lang == "go" and go_mod_content and not imp.is_relative:
                # Go uses module paths, not relative imports
                resolved = resolve_go_import(
                    imp.source, go_mod_content, available_files, root_dir,
                )
            elif lang == "python":
                resolved = resolve_python_import(
                    file_path, imp.source, available_files,
                    is_relative=imp.is_relative,
                )
            elif imp.is_relative or imp.source.startswith("."):
                # TS/JS/Rust/Java relative imports
                resolved = resolve_import(
                    file_path, imp.source, available_files, root_dir,
                    is_relative=True,
                )

            if resolved and resolved != file_path and resolved in available_files:
                graph.add_edge(Edge(
                    source=file_path,
                    target=resolved,
                    edge_type="imports",
                ))

    return graph


def get_blast_radius_v2(
    graph: CodeGraph,
    node_id: str,
    max_depth: int = 3,
    max_files: int = 50,
    include_tests: bool = True,
) -> BlastRadiusResult:
    """Compute enhanced blast radius with depth limiting and test separation.

    Uses BFS on reverse dependency edges. Test files are collected but
    not traversed further (they are leaf nodes in the blast radius).

    Args:
        graph: The CodeGraph to analyze.
        node_id: File path of the changed node.
        max_depth: Maximum BFS depth (default 3).
        max_files: Cap on total files in result (default 50).
        include_tests: Whether to include test files (default True).

    Returns:
        BlastRadiusResult with separated files, test_files, depth, and cap info.
    """
    result = BlastRadiusResult(changed_files=[node_id])

    if graph.get_node(node_id) is None:
        return result

    # BFS with depth tracking
    visited: set[str] = {node_id}
    dependents: list[str] = []
    test_files: list[str] = []
    actual_depth = 0

    queue: list[str] = [node_id]

    for depth in range(max_depth):
        next_queue: list[str] = []

        for current in queue:
            for dependent in graph.get_dependents(current):
                if dependent in visited:
                    continue

                if is_test_file(dependent):
                    if include_tests and dependent not in test_files:
                        test_files.append(dependent)
                    # Test files are NOT traversed further
                    continue

                visited.add(dependent)
                dependents.append(dependent)
                next_queue.append(dependent)

        if next_queue:
            actual_depth = depth + 1
        queue = next_queue

        if not queue:
            break

    # Post-BFS: collect test files that depend on any visited file
    if include_tests:
        for file_id in list(visited):
            for dependent in graph.get_dependents(file_id):
                if dependent not in visited and is_test_file(dependent):
                    if dependent not in test_files:
                        test_files.append(dependent)

    # Check cap
    total = len(dependents) + len(test_files)
    exceeded_cap = total > max_files

    result.files = dependents
    result.test_files = test_files
    result.depth = actual_depth
    result.exceeded_cap = exceeded_cap

    return result


# ---------------------------------------------------------------------------
# Import resolution (v1 — used by build_graph)
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
# Community detection (label propagation)
# ---------------------------------------------------------------------------

def _infer_community_name(nodes: list[Node]) -> str:
    """Infer a descriptive name for a community from its member nodes.

    Heuristics (in order of preference):
      1. Majority layer — if >50% of nodes share a layer, use it
      2. Common directory prefix — longest shared directory prefix
      3. Common name stem — shared prefix in node names
      4. Fallback — "cluster-N" (caller must supply N)
    """
    if not nodes:
        return ""

    # 1. Majority layer
    layer_counts: dict[str, int] = {}
    for n in nodes:
        if n.layer:
            layer_counts[n.layer] = layer_counts.get(n.layer, 0) + 1
    if layer_counts:
        best_layer, best_count = max(layer_counts.items(), key=lambda x: x[0] if x[1] == max(layer_counts.values()) else "")
        # Recalculate correctly: find the max count, then pick deterministically
        max_count = max(layer_counts.values())
        candidates = sorted(k for k, v in layer_counts.items() if v == max_count)
        if max_count > len(nodes) / 2:
            return candidates[0]

    # 2. Common directory prefix
    paths = [n.file_path for n in nodes if n.file_path]
    if paths:
        parts_list = [p.replace("\\", "/").split("/") for p in paths]
        # Find longest common prefix of directory parts (exclude filename)
        dir_parts = [p[:-1] for p in parts_list if len(p) > 1]
        if dir_parts:
            prefix_parts: list[str] = []
            for segments in zip(*dir_parts):
                if len(set(segments)) == 1:
                    prefix_parts.append(segments[0])
                else:
                    break
            if prefix_parts:
                return "/".join(prefix_parts)

    # 3. Common name stem (at least 3 chars)
    names = sorted(n.name for n in nodes if n.name)
    if len(names) >= 2:
        first, last = names[0], names[-1]
        common = 0
        for a, b in zip(first, last):
            if a == b:
                common += 1
            else:
                break
        if common >= 3:
            return first[:common].rstrip("_-")

    # 4. Fallback — empty string; caller adds "cluster-N"
    return ""


def detect_communities(
    graph: CodeGraph,
    max_iterations: int = 50,
) -> dict[str, list[str]]:
    """Detect communities using label propagation on import/depends_on edges.

    Each module node starts with its own label. On each iteration, every node
    adopts the most frequent label among its neighbors (connected via
    imports/depends_on edges in either direction). Ties are broken
    deterministically by choosing the lexicographically smallest label.

    Converges when no labels change or max_iterations is reached.

    Args:
        graph: The CodeGraph to analyze.
        max_iterations: Safety cap on iterations (default 50).

    Returns:
        dict mapping community_name → list of node IDs.
        Community names are inferred from member characteristics.
    """
    # Only operate on module nodes
    module_ids = [n.id for n in graph.nodes if n.node_type == "module"]
    if not module_ids:
        return {}

    # Build adjacency (undirected) from import/depends_on edges
    neighbors: dict[str, list[str]] = {nid: [] for nid in module_ids}
    module_set = set(module_ids)

    for e in graph.edges:
        if e.edge_type not in ("imports", "depends_on"):
            continue
        if e.source in module_set and e.target in module_set:
            neighbors[e.source].append(e.target)
            neighbors[e.target].append(e.source)

    # Initialize labels: each node is its own label
    labels: dict[str, str] = {nid: nid for nid in module_ids}

    # Iterate
    for _ in range(max_iterations):
        changed = False
        # Process nodes in deterministic order
        for nid in sorted(module_ids):
            nbrs = neighbors[nid]
            if not nbrs:
                continue

            # Count neighbor labels
            label_counts: dict[str, int] = {}
            for nbr in nbrs:
                lbl = labels[nbr]
                label_counts[lbl] = label_counts.get(lbl, 0) + 1

            # Find max frequency, break ties with sorted
            max_freq = max(label_counts.values())
            best_label = sorted(
                lbl for lbl, cnt in label_counts.items() if cnt == max_freq
            )[0]

            if labels[nid] != best_label:
                labels[nid] = best_label
                changed = True

        if not changed:
            break

    # Group by label
    groups: dict[str, list[str]] = {}
    for nid, lbl in labels.items():
        groups.setdefault(lbl, []).append(nid)

    # Sort members within each group for determinism
    for lbl in groups:
        groups[lbl].sort()

    # Name communities
    result: dict[str, list[str]] = {}
    cluster_counter = 0
    for lbl in sorted(groups.keys()):
        members = groups[lbl]
        member_nodes = [graph.get_node(nid) for nid in members]
        member_nodes = [n for n in member_nodes if n is not None]

        name = _infer_community_name(member_nodes)
        if not name:
            cluster_counter += 1
            name = f"cluster-{cluster_counter}"

        # Handle name collisions
        original_name = name
        suffix = 2
        while name in result:
            name = f"{original_name}-{suffix}"
            suffix += 1

        result[name] = members

    return result


def assign_communities(graph: CodeGraph, communities: dict[str, list[str]] | None = None) -> CodeGraph:
    """Run community detection and assign node.community fields.

    If communities dict is not provided, runs detect_communities() first.

    Args:
        graph: The CodeGraph to modify (in-place).
        communities: Optional pre-computed communities dict.

    Returns:
        The same graph with node.community fields set.
    """
    if communities is None:
        communities = detect_communities(graph)

    for community_name, node_ids in communities.items():
        for nid in node_ids:
            node = graph.get_node(nid)
            if node is not None:
                node.community = community_name

    return graph


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
