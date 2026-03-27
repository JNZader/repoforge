"""
PageRank scoring for code dependency graphs.

Implements a simple power iteration PageRank — NO external dependencies
(no NetworkX, no scipy). Works directly on CodeGraph adjacency data.

Higher rank = more important in the dependency graph.
Entry points and heavily-imported modules naturally bubble up.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..graph import CodeGraph

logger = logging.getLogger(__name__)


def pagerank(
    graph: "CodeGraph",
    damping: float = 0.85,
    iterations: int = 20,
) -> dict[str, float]:
    """Compute PageRank scores for all module nodes in a CodeGraph.

    Uses simple power iteration on the adjacency structure.
    Only considers "imports" and "depends_on" edges (skips "contains").

    Algorithm:
      1. Initialize all nodes with score 1/N
      2. For each iteration:
         score[node] = (1-d)/N + d * sum(score[referrer] / out_degree[referrer])
      3. Normalize scores to sum to 1.0

    Args:
        graph: A CodeGraph with nodes and edges.
        damping: Damping factor (default 0.85, classic PageRank value).
        iterations: Number of power iterations (default 20, sufficient for convergence).

    Returns:
        Dict mapping node_id -> rank score. Scores sum to 1.0.
        Empty dict for empty graphs.
    """
    # Collect module nodes only
    module_ids = [n.id for n in graph.nodes if n.node_type == "module"]
    n = len(module_ids)

    if n == 0:
        return {}

    if n == 1:
        return {module_ids[0]: 1.0}

    module_set = set(module_ids)

    # Build adjacency: outgoing edges per node and incoming edges per node
    # Only consider import/depends_on edges between module nodes
    out_degree: dict[str, int] = {mid: 0 for mid in module_ids}
    incoming: dict[str, list[str]] = {mid: [] for mid in module_ids}

    for edge in graph.edges:
        if edge.edge_type not in ("imports", "depends_on"):
            continue
        if edge.source not in module_set or edge.target not in module_set:
            continue
        # source imports target -> target gets a "vote" from source
        # In PageRank terms: source links TO target, so source's rank flows to target
        out_degree[edge.source] = out_degree.get(edge.source, 0) + 1
        incoming[edge.target].append(edge.source)

    # Initialize scores
    scores: dict[str, float] = {mid: 1.0 / n for mid in module_ids}

    # Power iteration
    base = (1.0 - damping) / n

    for _ in range(iterations):
        new_scores: dict[str, float] = {}
        for node_id in module_ids:
            rank_sum = 0.0
            for referrer in incoming[node_id]:
                deg = out_degree[referrer]
                if deg > 0:
                    rank_sum += scores[referrer] / deg
            new_scores[node_id] = base + damping * rank_sum
        scores = new_scores

    # Normalize to sum to 1.0
    total = sum(scores.values())
    if total > 0:
        scores = {k: v / total for k, v in scores.items()}

    return scores


def rank_files(
    graph: "CodeGraph",
    damping: float = 0.85,
    iterations: int = 20,
) -> list[tuple[str, float]]:
    """Compute PageRank and return files sorted by score descending.

    Convenience wrapper over pagerank() for when you need an ordered list.

    Args:
        graph: A CodeGraph with nodes and edges.
        damping: Damping factor.
        iterations: Number of power iterations.

    Returns:
        List of (node_id, score) tuples sorted by score descending.
    """
    scores = pagerank(graph, damping=damping, iterations=iterations)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
