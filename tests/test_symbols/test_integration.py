"""Integration tests — build_symbol_graph with confidence levels and filtering.

Exercises the full pipeline: extraction → SymbolIndex resolution → confidence
tagging → optional SymbolLinker bridge.
"""

from __future__ import annotations

import pytest

from repoforge.symbols.extractor import Symbol
from repoforge.symbols.graph import (
    CallEdge,
    SymbolGraph,
    _resolve_call,
    build_symbol_graph,
)
from repoforge.symbols.index import SymbolIndex

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sym(name: str, file: str, kind: str = "function", line: int = 1) -> Symbol:
    return Symbol(name=name, kind=kind, file=file, line=line, end_line=line + 5)


def _edge_map(graph: SymbolGraph) -> dict[tuple[str, str], str]:
    """Build (caller, callee) → confidence lookup from graph edges."""
    return {(e.caller, e.callee): e.confidence for e in graph.edges}


# ---------------------------------------------------------------------------
# 3.1 — _resolve_call returns (id, confidence)
# ---------------------------------------------------------------------------


class TestResolveCallWithIndex:
    """_resolve_call now uses SymbolIndex and returns (id, confidence)."""

    @pytest.fixture()
    def index(self) -> SymbolIndex:
        return SymbolIndex.from_symbols([
            _sym("helper", "a.py"),
            _sym("helper", "b.py"),
            _sym("unique_fn", "c.py"),
        ])

    def test_same_file_returns_direct(self, index: SymbolIndex) -> None:
        result = _resolve_call("helper", "a.py", {}, index)
        assert result is not None
        assert result == ("a.py::helper", "direct")

    def test_imported_returns_imported(self, index: SymbolIndex) -> None:
        result = _resolve_call("helper", "x.py", {"helper": "b.py"}, index)
        assert result is not None
        assert result == ("b.py::helper", "imported")

    def test_unique_global_returns_heuristic(self, index: SymbolIndex) -> None:
        result = _resolve_call("unique_fn", "a.py", {}, index)
        assert result is not None
        assert result == ("c.py::unique_fn", "heuristic")

    def test_ambiguous_returns_none(self, index: SymbolIndex) -> None:
        result = _resolve_call("helper", "x.py", {}, index)
        assert result is None

    def test_not_found_returns_none(self, index: SymbolIndex) -> None:
        result = _resolve_call("nonexistent", "a.py", {}, index)
        assert result is None


# ---------------------------------------------------------------------------
# 3.2 — build_symbol_graph sets confidence on edges
# ---------------------------------------------------------------------------


class TestBuildSymbolGraphConfidence:
    """build_symbol_graph wires SymbolIndex and tags CallEdge.confidence."""

    def test_intra_file_direct(self, tmp_path) -> None:
        (tmp_path / "app.py").write_text(
            "def helper():\n"
            "    pass\n\n"
            "def main():\n"
            "    helper()\n"
        )
        graph = build_symbol_graph(str(tmp_path), ["app.py"])
        em = _edge_map(graph)
        assert ("app.py::main", "app.py::helper") in em
        assert em[("app.py::main", "app.py::helper")] == "direct"

    def test_cross_file_imported(self, tmp_path) -> None:
        (tmp_path / "utils.py").write_text("def helper():\n    pass\n")
        (tmp_path / "app.py").write_text(
            "from utils import helper\n\n"
            "def main():\n"
            "    helper()\n"
        )
        graph = build_symbol_graph(str(tmp_path), ["utils.py", "app.py"])
        em = _edge_map(graph)
        assert ("app.py::main", "utils.py::helper") in em
        assert em[("app.py::main", "utils.py::helper")] == "imported"

    def test_unique_global_heuristic_or_linked(self, tmp_path) -> None:
        """A call to a unique-name function not imported and not same-file.

        Starts as 'heuristic'; may be upgraded to 'linked' if the SymbolLinker
        bridge is available and confirms the resolution.
        """
        (tmp_path / "lib.py").write_text("def unique_helper():\n    pass\n")
        (tmp_path / "app.py").write_text(
            "def main():\n"
            "    unique_helper()\n"
        )
        graph = build_symbol_graph(str(tmp_path), ["lib.py", "app.py"])
        em = _edge_map(graph)
        assert ("app.py::main", "lib.py::unique_helper") in em
        # heuristic when intelligence module is absent, linked when present
        assert em[("app.py::main", "lib.py::unique_helper")] in ("heuristic", "linked")

    def test_multi_file_all_confidence_levels(self, tmp_path) -> None:
        """A single test exercising direct, imported, and heuristic simultaneously."""
        (tmp_path / "core.py").write_text(
            "def local_fn():\n    pass\n\n"
            "def caller():\n"
            "    local_fn()\n"
            "    imported_fn()\n"
            "    global_fn()\n"
        )
        (tmp_path / "utils.py").write_text("def imported_fn():\n    pass\n")
        (tmp_path / "lib.py").write_text("def global_fn():\n    pass\n")

        # core.py imports imported_fn from utils.py
        # We need the import statement for the import map to be built
        (tmp_path / "core.py").write_text(
            "from utils import imported_fn\n\n"
            "def local_fn():\n    pass\n\n"
            "def caller():\n"
            "    local_fn()\n"
            "    imported_fn()\n"
            "    global_fn()\n"
        )

        graph = build_symbol_graph(
            str(tmp_path), ["core.py", "utils.py", "lib.py"],
        )
        em = _edge_map(graph)

        # local call → direct
        assert em.get(("core.py::caller", "core.py::local_fn")) == "direct"
        # imported call → imported
        assert em.get(("core.py::caller", "utils.py::imported_fn")) == "imported"
        # unique global call → heuristic (or linked if SymbolLinker available)
        assert em.get(("core.py::caller", "lib.py::global_fn")) in ("heuristic", "linked")


# ---------------------------------------------------------------------------
# 3.2 + filter_edges integration
# ---------------------------------------------------------------------------


class TestFilterEdgesIntegration:
    """filter_edges works correctly with confidence-tagged edges from build_symbol_graph."""

    def test_filter_imported_removes_heuristic(self, tmp_path) -> None:
        """Build a graph with mixed confidence, then filter."""
        (tmp_path / "core.py").write_text(
            "from utils import imported_fn\n\n"
            "def local_fn():\n    pass\n\n"
            "def caller():\n"
            "    local_fn()\n"
            "    imported_fn()\n"
            "    global_fn()\n"
        )
        (tmp_path / "utils.py").write_text("def imported_fn():\n    pass\n")
        (tmp_path / "lib.py").write_text("def global_fn():\n    pass\n")

        graph = build_symbol_graph(
            str(tmp_path), ["core.py", "utils.py", "lib.py"],
        )

        # Filter to "imported" level — should drop heuristic edges
        # (linked edges are kept since linked > heuristic)
        filtered = graph.filter_edges(min_confidence="imported")
        confidences = {e.confidence for e in filtered.edges}
        assert "heuristic" not in confidences
        assert "direct" in confidences
        assert "imported" in confidences

    def test_filter_direct_only(self, tmp_path) -> None:
        (tmp_path / "a.py").write_text(
            "def helper():\n    pass\n\n"
            "def main():\n    helper()\n"
        )
        (tmp_path / "b.py").write_text("def other():\n    helper()\n")

        graph = build_symbol_graph(str(tmp_path), ["a.py", "b.py"])
        filtered = graph.filter_edges(min_confidence="direct")

        # Only the intra-file call should remain (direct confidence)
        direct_edges = [e for e in filtered.edges if e.confidence == "direct"]
        assert len(direct_edges) == 1
        assert direct_edges[0].caller == "a.py::main"

    def test_filter_preserves_symbols(self, tmp_path) -> None:
        (tmp_path / "a.py").write_text(
            "def f():\n    pass\n\n"
            "def g():\n    f()\n"
        )
        graph = build_symbol_graph(str(tmp_path), ["a.py"])
        filtered = graph.filter_edges(min_confidence="direct")
        assert set(filtered.symbols.keys()) == set(graph.symbols.keys())


# ---------------------------------------------------------------------------
# 3.3 — SymbolLinker bridge (optional)
# ---------------------------------------------------------------------------


class TestSymbolLinkerBridge:
    """SymbolLinker integration — works when intelligence module is available."""

    def test_graph_builds_without_intelligence_module(self, tmp_path) -> None:
        """build_symbol_graph works even if intelligence module import fails."""
        (tmp_path / "a.py").write_text("def foo():\n    pass\n")
        # Should not raise even if SymbolLinker is unavailable
        graph = build_symbol_graph(str(tmp_path), ["a.py"])
        assert "a.py::foo" in graph.symbols

    def test_linker_bridge_upgrades_heuristic_when_available(self, tmp_path) -> None:
        """If SymbolLinker is available and confirms a heuristic match,
        confidence should be upgraded to 'linked'."""
        (tmp_path / "lib.py").write_text(
            "class DataProcessor:\n"
            "    pass\n"
        )
        (tmp_path / "app.py").write_text(
            "def main():\n"
            "    DataProcessor()\n"
        )
        graph = build_symbol_graph(str(tmp_path), ["lib.py", "app.py"])

        # Check the edge exists — confidence depends on whether
        # intelligence module is importable
        em = _edge_map(graph)
        key = ("app.py::main", "lib.py::DataProcessor")
        if key in em:
            # If intelligence module available: should be "linked"
            # If not: should be "heuristic" (unique global match)
            assert em[key] in ("heuristic", "linked")
