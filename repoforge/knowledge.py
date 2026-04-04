"""Knowledge Graph extensions — architecture pattern detection and diagram generation.

Analyzes a CodeGraph to detect architectural patterns (layered, MVC,
multi-layer, circular dependencies) and generates focused Mermaid
diagrams for documentation chapters.

Usage:
    from repoforge.knowledge import detect_architecture_patterns, generate_architecture_mermaid
    patterns = detect_architecture_patterns(graph)
    mermaid = generate_architecture_mermaid(graph)
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field

from .graph import CodeGraph, Edge, Node

logger = logging.getLogger(__name__)


@dataclass
class ArchitecturePattern:
    """A detected architectural pattern with confidence score."""

    name: str               # "layered", "multi_layer", "circular_deps", "hub_spoke"
    confidence: float       # 0.0 to 1.0
    description: str
    layers: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------


def detect_architecture_patterns(graph: CodeGraph) -> list[ArchitecturePattern]:
    """Analyze graph structure and detect architectural patterns."""
    if not graph.nodes:
        return []

    patterns: list[ArchitecturePattern] = []

    # Only analyze module nodes with import edges
    modules = [n for n in graph.nodes if n.node_type == "module"]
    import_edges = [e for e in graph.edges if e.edge_type in ("imports", "depends_on")]

    if not modules:
        return []

    _detect_layered(modules, import_edges, patterns)
    _detect_multi_layer(modules, patterns)
    _detect_circular(modules, import_edges, patterns)
    _detect_hub_spoke(modules, import_edges, patterns)

    # Sort by confidence descending
    patterns.sort(key=lambda p: p.confidence, reverse=True)
    return patterns


def _detect_layered(modules: list[Node], edges: list[Edge], patterns: list) -> None:
    """Detect layered architecture — unidirectional dependency flow.

    A layered architecture has modules where dependencies only flow
    in one direction (e.g., handlers → service → store → models).
    """
    if len(modules) < 3:
        return

    # Build adjacency: who imports whom
    imports: dict[str, set[str]] = defaultdict(set)
    imported_by: dict[str, set[str]] = defaultdict(set)
    module_ids = {m.id for m in modules}

    for e in edges:
        if e.source in module_ids and e.target in module_ids:
            imports[e.source].add(e.target)
            imported_by[e.target].add(e.source)

    # Find topological layers via in-degree analysis
    # Modules with no incoming imports are the "top" layer
    in_degree = {m.id: len(imported_by.get(m.id, set())) for m in modules}
    out_degree = {m.id: len(imports.get(m.id, set())) for m in modules}

    # Top layer: high out-degree, low in-degree (entry points/handlers)
    top = [m for m in modules if in_degree[m.id] == 0 and out_degree[m.id] > 0]
    # Bottom layer: high in-degree, low out-degree (models/utils)
    bottom = [m for m in modules if out_degree[m.id] == 0 and in_degree[m.id] > 0]
    # Middle: everything else with both in and out
    middle = [m for m in modules
              if in_degree[m.id] > 0 and out_degree[m.id] > 0]

    if top and bottom:
        layer_names = (
            [m.name for m in top[:3]]
            + [m.name for m in middle[:3]]
            + [m.name for m in bottom[:3]]
        )

        # Check for back-edges (bottom importing top = violation)
        violations = 0
        top_ids = {m.id for m in top}
        bottom_ids = {m.id for m in bottom}
        for e in edges:
            if e.source in bottom_ids and e.target in top_ids:
                violations += 1

        total_edges = len(edges) or 1
        violation_ratio = violations / total_edges
        confidence = max(0.0, 0.9 - violation_ratio * 2)

        if confidence >= 0.3:
            patterns.append(ArchitecturePattern(
                name="layered",
                confidence=round(confidence, 2),
                description="Unidirectional dependency flow from entry points to data layer",
                layers=layer_names,
                details={
                    "top_layer": [m.name for m in top],
                    "middle_layer": [m.name for m in middle],
                    "bottom_layer": [m.name for m in bottom],
                    "violations": violations,
                },
            ))


def _detect_multi_layer(modules: list[Node], patterns: list) -> None:
    """Detect multi-layer/monorepo architecture from explicit layer assignments."""
    layers = defaultdict(list)
    for m in modules:
        if m.layer:
            layers[m.layer].append(m.name)

    if len(layers) >= 2:
        patterns.append(ArchitecturePattern(
            name="multi_layer",
            confidence=0.9,
            description=f"Explicit layer separation: {', '.join(sorted(layers.keys()))}",
            layers=sorted(layers.keys()),
            details={k: v for k, v in sorted(layers.items())},
        ))


def _detect_circular(modules: list[Node], edges: list[Edge], patterns: list) -> None:
    """Detect circular dependencies via DFS cycle detection."""
    module_ids = {m.id for m in modules}
    adj: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        if e.source in module_ids and e.target in module_ids:
            adj[e.source].append(e.target)

    visited: set[str] = set()
    in_stack: set[str] = set()
    cycles: list[tuple[str, str]] = []

    def dfs(node: str) -> None:
        visited.add(node)
        in_stack.add(node)
        for neighbor in adj.get(node, []):
            if neighbor in in_stack:
                cycles.append((node, neighbor))
            elif neighbor not in visited:
                dfs(node=neighbor)
        in_stack.discard(node)

    for m in modules:
        if m.id not in visited:
            dfs(m.id)

    if cycles:
        patterns.append(ArchitecturePattern(
            name="circular_deps",
            confidence=round(min(1.0, len(cycles) * 0.3), 2),
            description=f"{len(cycles)} circular dependency(ies) detected",
            details={"cycles": [(a, b) for a, b in cycles[:10]]},
        ))


def _detect_hub_spoke(modules: list[Node], edges: list[Edge], patterns: list) -> None:
    """Detect hub-and-spoke pattern — one module imported by many others."""
    module_ids = {m.id for m in modules}
    imported_by_count: dict[str, int] = defaultdict(int)

    for e in edges:
        if e.target in module_ids:
            imported_by_count[e.target] += 1

    if not imported_by_count:
        return

    max_importers = max(imported_by_count.values())
    threshold = max(3, len(modules) * 0.4)

    if max_importers >= threshold:
        hubs = [
            mid for mid, count in imported_by_count.items()
            if count >= threshold
        ]
        id_to_name = {m.id: m.name for m in modules}
        hub_names = [id_to_name.get(h, h) for h in hubs]

        patterns.append(ArchitecturePattern(
            name="hub_spoke",
            confidence=round(min(1.0, max_importers / len(modules)), 2),
            description=f"Hub module(s) imported by many: {', '.join(hub_names)}",
            layers=hub_names,
            details={"hubs": {h: imported_by_count[h] for h in hubs}},
        ))


# ---------------------------------------------------------------------------
# Mermaid diagram generation for documentation
# ---------------------------------------------------------------------------


def generate_architecture_mermaid(graph: CodeGraph, max_nodes: int = 30) -> str:
    """Generate a focused architecture Mermaid diagram for documentation.

    Groups modules by layer (if available) into subgraphs.
    Shows import relationships as arrows.
    """
    modules = [n for n in graph.nodes if n.node_type == "module"]
    import_edges = [e for e in graph.edges if e.edge_type in ("imports", "depends_on")]

    if not modules:
        return ""

    # Group by layer
    layers: dict[str, list[Node]] = defaultdict(list)
    for m in modules[:max_nodes]:
        layers[m.layer or "main"].append(m)

    lines = ["graph TD"]

    if len(layers) > 1:
        # Multi-layer: use subgraphs
        for layer_name, layer_modules in sorted(layers.items()):
            safe_layer = _safe_id(layer_name)
            lines.append(f"    subgraph {safe_layer}[\"{layer_name}\"]")
            for m in layer_modules:
                lines.append(f"        {_safe_id(m.id)}[\"{m.name}\"]")
            lines.append("    end")
    else:
        # Single layer: flat nodes
        for m in modules[:max_nodes]:
            lines.append(f"    {_safe_id(m.id)}[\"{m.name}\"]")

    # Edges
    node_ids = {m.id for m in modules[:max_nodes]}
    for e in import_edges:
        if e.source in node_ids and e.target in node_ids:
            lines.append(f"    {_safe_id(e.source)} --> {_safe_id(e.target)}")

    return "\n".join(lines)


def _safe_id(raw: str) -> str:
    """Convert a file path to a valid Mermaid node ID."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw)
