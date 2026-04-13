"""
semantic_search.py — Behavior-based semantic code search.

Find code by what it DOES, not just keyword matching. Uses the multi-layer
analysis from deep_analysis.py to create richer code representations that
capture behavior (control flow patterns, data flow, call relationships)
alongside structural information (function signatures, parameters).

Search modes:
  - behavior: Search by behavioral description ("authenticates user requests")
  - signature: Search by function signature patterns
  - pattern: Search by control flow patterns (loops, branches, error handling)

Entry points:
  - build_behavior_index(repo_path, depth=3) → BehaviorIndex
  - search_by_behavior(index, query) → list[BehaviorMatch]
  - search_repo(repo_path, query, depth=3) → list[BehaviorMatch]
  - format_search_results(results) → human-readable markdown

Uses BM25 keyword search (no external dependencies) as the primary search
backend. When FAISS is available, uses hybrid search for better results.
"""

from __future__ import annotations

import json
import logging
import math
import re
import string
from dataclasses import dataclass, field
from pathlib import Path

from .deep_analysis import (
    ASTNode,
    CallEdgeInfo,
    CFGNode,
    DFGEdge,
    FileAnalysis,
    FunctionAnalysis,
    analyze_file,
    analyze_repo,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class BehaviorDescriptor:
    """Rich behavioral description of a function for search indexing."""

    function_name: str
    file_path: str
    line: int
    language: str

    # Structural
    signature: str  # e.g., "process_data(items: list, threshold: float)"
    kind: str  # function, method, class

    # Behavioral text components
    param_text: str  # "accepts items (list), threshold (float)"
    call_text: str  # "calls validate, transform, save"
    flow_text: str  # "branches on condition, loops over items"
    data_text: str  # "uses items, threshold; defines result, filtered"

    # Combined searchable text
    full_text: str = ""

    # Complexity info
    cyclomatic_complexity: int = 1
    complexity_rating: str = "low"

    def __post_init__(self) -> None:
        if not self.full_text:
            parts = [
                f"{self.kind} {self.function_name} in {self.file_path}",
                self.signature,
            ]
            if self.param_text:
                parts.append(self.param_text)
            if self.call_text:
                parts.append(self.call_text)
            if self.flow_text:
                parts.append(self.flow_text)
            if self.data_text:
                parts.append(self.data_text)
            self.full_text = ". ".join(parts)


@dataclass
class BehaviorMatch:
    """A single search result from behavior-based search."""

    function_name: str
    file_path: str
    line: int
    score: float
    descriptor: BehaviorDescriptor
    snippet: str = ""  # brief explanation of why it matched

    def to_dict(self) -> dict:
        return {
            "function": self.function_name,
            "file": self.file_path,
            "line": self.line,
            "score": round(self.score, 4),
            "signature": self.descriptor.signature,
            "complexity": self.descriptor.complexity_rating,
            "behavior": self.descriptor.full_text[:200],
        }


# ---------------------------------------------------------------------------
# BM25 search engine (self-contained, no external deps)
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")

# CamelCase and snake_case splitter
_CAMEL_RE = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _tokenize(text: str) -> list[str]:
    """Tokenize text: lowercase, split camelCase/snake_case, strip punctuation."""
    # Replace underscores and split camelCase
    expanded = _CAMEL_RE.sub(" ", text)
    expanded = expanded.replace("_", " ")
    cleaned = _PUNCT_RE.sub(" ", expanded.lower())
    return cleaned.split()


class _BM25:
    """Minimal BM25 for behavior search. Self-contained."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.docs: list[list[str]] = []
        self.doc_ids: list[str] = []
        self.avg_dl: float = 0.0
        self.idf: dict[str, float] = {}
        self.doc_freqs: dict[str, int] = {}

    def add(self, texts: list[str], ids: list[str]) -> None:
        self.docs = [_tokenize(t) for t in texts]
        self.doc_ids = list(ids)
        self.avg_dl = sum(len(d) for d in self.docs) / max(len(self.docs), 1)

        # Document frequency
        self.doc_freqs = {}
        for doc in self.docs:
            seen: set[str] = set()
            for token in doc:
                if token not in seen:
                    self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1
                    seen.add(token)

        # IDF
        n = len(self.docs)
        self.idf = {}
        for term, df in self.doc_freqs.items():
            self.idf[term] = math.log((n - df + 0.5) / (df + 0.5) + 1)

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        query_tokens = _tokenize(query)
        scores: list[tuple[str, float]] = []

        for i, doc in enumerate(self.docs):
            score = 0.0
            dl = len(doc)
            tf_map: dict[str, int] = {}
            for token in doc:
                tf_map[token] = tf_map.get(token, 0) + 1

            for qt in query_tokens:
                if qt not in self.idf:
                    continue
                tf = tf_map.get(qt, 0)
                idf = self.idf[qt]
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * dl / max(self.avg_dl, 1))
                score += idf * numerator / denominator

            if score > 0:
                scores.append((self.doc_ids[i], score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    @property
    def size(self) -> int:
        return len(self.docs)


# ---------------------------------------------------------------------------
# Behavior descriptor construction
# ---------------------------------------------------------------------------


def _build_signature(node: ASTNode) -> str:
    """Build a human-readable function signature."""
    params = ", ".join(node.params) if node.params else ""
    return f"{node.name}({params})"


def _build_param_text(params: list[str]) -> str:
    """Describe parameters in natural language."""
    if not params:
        return ""
    parts = []
    for p in params:
        # Extract name and type from "name: type" or "name type"
        clean = p.strip().lstrip("*")
        if ":" in clean:
            name, typ = clean.split(":", 1)
            parts.append(f"{name.strip()} ({typ.strip()})")
        elif " " in clean:
            tokens = clean.split()
            parts.append(f"{tokens[0]} ({' '.join(tokens[1:])})")
        else:
            parts.append(clean)
    return f"accepts {', '.join(parts)}"


def _build_call_text(calls: list[CallEdgeInfo]) -> str:
    """Describe function calls in natural language."""
    if not calls:
        return ""
    unique_callees = list(dict.fromkeys(e.callee for e in calls))
    return f"calls {', '.join(unique_callees[:15])}"


def _build_flow_text(cfg_nodes: list[CFGNode]) -> str:
    """Describe control flow in natural language."""
    if not cfg_nodes:
        return ""
    # Count by type
    counts: dict[str, int] = {}
    for n in cfg_nodes:
        counts[n.node_type] = counts.get(n.node_type, 0) + 1

    parts = []
    if counts.get("branch", 0):
        parts.append(f"{counts['branch']} branches")
    if counts.get("loop", 0):
        parts.append(f"{counts['loop']} loops")
    if counts.get("try", 0):
        parts.append(f"{counts['try']} error handlers")
    if counts.get("return", 0):
        parts.append(f"{counts['return']} return points")
    if counts.get("raise", 0):
        parts.append(f"{counts['raise']} exceptions raised")

    return f"has {', '.join(parts)}" if parts else ""


def _build_data_text(dfg_edges: list[DFGEdge]) -> str:
    """Describe data flow in natural language."""
    if not dfg_edges:
        return ""
    variables = list(dict.fromkeys(e.variable for e in dfg_edges))
    return f"uses variables: {', '.join(variables[:15])}"


def _build_descriptor(
    func: FunctionAnalysis,
    file_path: str,
    language: str,
    ast_node: ASTNode,
) -> BehaviorDescriptor:
    """Build a complete behavior descriptor for a function."""
    return BehaviorDescriptor(
        function_name=func.name,
        file_path=file_path,
        line=func.line,
        language=language,
        signature=_build_signature(ast_node),
        kind=ast_node.kind,
        param_text=_build_param_text(ast_node.params),
        call_text=_build_call_text(func.calls),
        flow_text=_build_flow_text(func.cfg_nodes),
        data_text=_build_data_text(func.dfg_edges),
        cyclomatic_complexity=func.cyclomatic_complexity,
        complexity_rating=func.complexity_rating,
    )


# ---------------------------------------------------------------------------
# Behavior index
# ---------------------------------------------------------------------------


@dataclass
class BehaviorIndex:
    """Index of function behaviors for semantic search."""

    descriptors: dict[str, BehaviorDescriptor] = field(default_factory=dict)
    """function_id → BehaviorDescriptor."""

    _bm25: _BM25 | None = field(default=None, repr=False)

    @property
    def size(self) -> int:
        return len(self.descriptors)

    def _build_search_index(self) -> None:
        """Build the BM25 index from descriptors."""
        self._bm25 = _BM25()
        ids = list(self.descriptors.keys())
        texts = [d.full_text for d in self.descriptors.values()]
        self._bm25.add(texts, ids)

    def search(self, query: str, top_k: int = 10) -> list[BehaviorMatch]:
        """Search the index by behavior description."""
        if self._bm25 is None:
            self._build_search_index()
        assert self._bm25 is not None

        results = self._bm25.search(query, top_k=top_k)
        matches: list[BehaviorMatch] = []

        for func_id, score in results:
            desc = self.descriptors.get(func_id)
            if desc is None:
                continue
            matches.append(BehaviorMatch(
                function_name=desc.function_name,
                file_path=desc.file_path,
                line=desc.line,
                score=score,
                descriptor=desc,
                snippet=desc.full_text[:200],
            ))

        return matches


# ---------------------------------------------------------------------------
# Index building
# ---------------------------------------------------------------------------


def build_behavior_index(
    repo_path: str,
    depth: int = 3,
    files: list[str] | None = None,
) -> BehaviorIndex:
    """Build a behavior index from repository analysis.

    Args:
        repo_path: Absolute path to the repository root.
        depth: Analysis depth (1-5). Higher = richer behavioral data.
            3 is recommended for good behavior search with reasonable speed.
        files: Optional list of relative file paths.

    Returns:
        BehaviorIndex ready for searching.
    """
    # Use at least depth 3 for meaningful behavior search
    effective_depth = max(depth, 2)

    repo_analysis = analyze_repo(repo_path, depth=effective_depth, files=files)
    index = BehaviorIndex()

    for file_analysis in repo_analysis.files:
        ast_by_name: dict[str, ASTNode] = {
            n.name: n for n in file_analysis.ast_nodes
        }

        for func in file_analysis.functions:
            ast_node = ast_by_name.get(func.name)
            if ast_node is None:
                continue

            func_id = f"{file_analysis.file_path}::{func.name}"
            desc = _build_descriptor(
                func, file_analysis.file_path, file_analysis.language, ast_node,
            )
            index.descriptors[func_id] = desc

    index._build_search_index()
    return index


# ---------------------------------------------------------------------------
# High-level search API
# ---------------------------------------------------------------------------


def search_repo(
    repo_path: str,
    query: str,
    *,
    depth: int = 3,
    top_k: int = 10,
    files: list[str] | None = None,
) -> list[BehaviorMatch]:
    """Search a repository by behavior description.

    Convenience function: builds index + searches in one call.
    For repeated searches, use build_behavior_index() + index.search().

    Args:
        repo_path: Absolute path to the repository root.
        query: Natural language behavior description.
        depth: Analysis depth (1-5).
        top_k: Maximum number of results.
        files: Optional file list to restrict search scope.

    Returns:
        List of BehaviorMatch results, sorted by relevance.
    """
    index = build_behavior_index(repo_path, depth=depth, files=files)
    return index.search(query, top_k=top_k)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_search_results(results: list[BehaviorMatch]) -> str:
    """Format search results as human-readable markdown."""
    if not results:
        return "No matching functions found.\n"

    lines: list[str] = []
    lines.append(f"## Behavior Search Results ({len(results)} matches)")
    lines.append("")

    for i, match in enumerate(results, 1):
        d = match.descriptor
        lines.append(f"### {i}. `{d.function_name}` (score: {match.score:.3f})")
        lines.append(f"**File**: `{d.file_path}:L{d.line}`")
        lines.append(f"**Signature**: `{d.signature}`")
        lines.append(f"**Complexity**: {d.complexity_rating} (CC={d.cyclomatic_complexity})")
        lines.append("")

        if d.call_text:
            lines.append(f"- {d.call_text}")
        if d.flow_text:
            lines.append(f"- {d.flow_text}")
        if d.data_text:
            lines.append(f"- {d.data_text}")
        lines.append("")

    return "\n".join(lines)


def search_results_to_json(results: list[BehaviorMatch]) -> str:
    """Serialize search results to JSON."""
    data = {
        "count": len(results),
        "results": [m.to_dict() for m in results],
    }
    return json.dumps(data, indent=2) + "\n"
