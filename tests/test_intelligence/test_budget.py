"""Tests for token-budgeted context selection (repoforge.intelligence.budget)."""

import os
import tempfile
from pathlib import Path

import pytest

from repoforge.graph import CodeGraph, Edge, Node
from repoforge.intelligence.ast_extractor import ASTSymbol
from repoforge.intelligence.budget import ContextItem, select_context

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_graph(nodes: list[str], edges: list[tuple[str, str]]) -> CodeGraph:
    """Build a simple module graph from node IDs and (src, tgt) edge pairs."""
    g = CodeGraph()
    for nid in nodes:
        g.add_node(Node(id=nid, name=Path(nid).stem, node_type="module", file_path=nid))
    for src, tgt in edges:
        g.add_edge(Edge(source=src, target=tgt, edge_type="imports"))
    return g


def _write_files(root: Path, files: dict[str, str]) -> None:
    """Write files to a temp directory."""
    for rel_path, content in files.items():
        full = root / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBudgetZero:
    """Edge case: zero or negative budget."""

    def test_budget_zero_returns_empty(self):
        """Budget of 0 -> empty selection."""
        g = _make_graph(["a.py"], [])
        result = select_context(g, {"a.py": 1.0}, "/tmp", budget_tokens=0)
        assert result == []

    def test_budget_negative_returns_empty(self):
        """Negative budget -> empty selection."""
        g = _make_graph(["a.py"], [])
        result = select_context(g, {"a.py": 1.0}, "/tmp", budget_tokens=-100)
        assert result == []


class TestBudgetRespected:
    """Budget never exceeded."""

    def test_total_tokens_within_budget(self):
        """Total token estimate never exceeds the budget."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with known content
            _write_files(Path(tmpdir), {
                "a.py": "x" * 400,  # ~100 tokens
                "b.py": "y" * 800,  # ~200 tokens
                "c.py": "z" * 1200, # ~300 tokens
            })
            g = _make_graph(["a.py", "b.py", "c.py"], [
                ("a.py", "b.py"),
                ("b.py", "c.py"),
            ])
            ranks = {"a.py": 0.1, "b.py": 0.3, "c.py": 0.6}

            result = select_context(g, ranks, tmpdir, budget_tokens=250)
            total = sum(item.token_estimate for item in result)
            assert total <= 250

    def test_truncation_respects_budget(self):
        """Large files get truncated to fit remaining budget."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_files(Path(tmpdir), {
                "small.py": "x" * 40,   # ~10 tokens
                "big.py": "y" * 40000,  # ~10000 tokens
            })
            g = _make_graph(["small.py", "big.py"], [])
            # small has higher rank -> selected first
            ranks = {"small.py": 0.7, "big.py": 0.3}

            result = select_context(g, ranks, tmpdir, budget_tokens=50)
            total = sum(item.token_estimate for item in result)
            assert total <= 50
            # small.py (~10 tokens) fits, big.py gets truncated
            paths = [item.file_path for item in result]
            assert "small.py" in paths


class TestEntryPointsAlwaysIncluded:
    """Entry points are selected first, even with tiny budget."""

    def test_entry_point_included_first(self):
        """main.py is included before higher-ranked non-entry files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_files(Path(tmpdir), {
                "main.py": "print('hello')",
                "core.py": "def process(): pass",
                "utils.py": "def helper(): pass",
            })
            g = _make_graph(["main.py", "core.py", "utils.py"], [
                ("main.py", "core.py"),
                ("core.py", "utils.py"),
            ])
            # core.py has higher rank but main.py is entry point
            ranks = {"main.py": 0.1, "core.py": 0.6, "utils.py": 0.3}

            result = select_context(g, ranks, tmpdir, budget_tokens=4000)
            assert len(result) >= 1
            assert result[0].file_path == "main.py"
            assert result[0].reason == "entry_point"

    def test_cli_py_detected_as_entry(self):
        """cli.py is recognized as an entry point."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_files(Path(tmpdir), {
                "cli.py": "import click",
                "lib.py": "def work(): pass",
            })
            g = _make_graph(["cli.py", "lib.py"], [("cli.py", "lib.py")])
            ranks = {"cli.py": 0.3, "lib.py": 0.7}

            result = select_context(g, ranks, tmpdir, budget_tokens=4000)
            entry_items = [i for i in result if i.reason == "entry_point"]
            assert any(i.file_path == "cli.py" for i in entry_items)


class TestRankOrdering:
    """Highest ranked files selected first (after entry points)."""

    def test_highest_rank_first(self):
        """Files with higher PageRank are selected before lower."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_files(Path(tmpdir), {
                "low.py": "x" * 40,
                "mid.py": "y" * 40,
                "high.py": "z" * 40,
            })
            g = _make_graph(["low.py", "mid.py", "high.py"], [])
            ranks = {"low.py": 0.1, "mid.py": 0.3, "high.py": 0.6}

            result = select_context(g, ranks, tmpdir, budget_tokens=4000)
            paths = [item.file_path for item in result]
            # Should be ordered by rank descending
            assert paths == ["high.py", "mid.py", "low.py"]

    def test_rank_scores_preserved(self):
        """ContextItem.rank_score matches the input ranks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_files(Path(tmpdir), {"a.py": "content"})
            g = _make_graph(["a.py"], [])
            ranks = {"a.py": 0.42}

            result = select_context(g, ranks, tmpdir, budget_tokens=4000)
            assert len(result) == 1
            assert result[0].rank_score == pytest.approx(0.42)


class TestASTSummaryMode:
    """AST summary uses fewer tokens than raw source."""

    def test_ast_summary_cheaper_than_raw(self):
        """When AST symbols provided, token cost is lower than full source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Large file
            source = "\n".join([
                "def process_data(items: list[str]) -> dict:",
                "    result = {}",
                "    for item in items:",
                "        result[item] = len(item)",
                "    return result",
                "",
                "def validate(data: dict) -> bool:",
                "    return bool(data)",
                "",
                "class DataProcessor:",
                "    def __init__(self):",
                "        self.cache = {}",
                "    def run(self):",
                "        pass",
            ])
            _write_files(Path(tmpdir), {"data.py": source})

            g = _make_graph(["data.py"], [])
            ranks = {"data.py": 0.5}

            # Without AST
            result_raw = select_context(g, ranks, tmpdir, budget_tokens=4000)

            # With AST symbols (signatures only)
            ast_symbols = {
                "data.py": [
                    ASTSymbol(
                        name="process_data", kind="function",
                        signature="def process_data(items: list[str]) -> dict",
                    ),
                    ASTSymbol(
                        name="validate", kind="function",
                        signature="def validate(data: dict) -> bool",
                    ),
                    ASTSymbol(
                        name="DataProcessor", kind="class",
                        signature="class DataProcessor",
                    ),
                ]
            }
            result_ast = select_context(
                g, ranks, tmpdir, budget_tokens=4000, ast_symbols=ast_symbols,
            )

            assert len(result_raw) == 1
            assert len(result_ast) == 1
            # AST summary should be cheaper
            assert result_ast[0].token_estimate < result_raw[0].token_estimate

    def test_ast_fallback_to_raw_when_no_symbols(self):
        """Files without AST symbols get raw source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_files(Path(tmpdir), {"a.py": "print('hello')"})
            g = _make_graph(["a.py"], [])
            ranks = {"a.py": 0.5}

            # Empty AST symbols for this file
            result = select_context(
                g, ranks, tmpdir, budget_tokens=4000,
                ast_symbols={"other.py": []},
            )
            assert len(result) == 1
            assert "print" in result[0].content


class TestEmptyGraph:
    """Empty graph edge cases."""

    def test_no_modules(self):
        """Graph with no module nodes returns empty."""
        g = CodeGraph()
        result = select_context(g, {}, "/tmp", budget_tokens=4000)
        assert result == []

    def test_unreadable_files(self):
        """Files that don't exist on disk are silently skipped."""
        g = _make_graph(["nonexistent.py"], [])
        ranks = {"nonexistent.py": 1.0}
        result = select_context(g, ranks, "/tmp/nonexistent_dir", budget_tokens=4000)
        assert result == []
