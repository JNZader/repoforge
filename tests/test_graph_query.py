"""
tests/test_graph_query.py — Tests for graph query interface.

Tests cover:
- QueryResult dataclass creation and to_json() serialization
- query_callers() with known/unknown symbols, multiple matches
- query_callees() with known/unknown symbols
- query_imports() with known/unknown files
- CLI --query integration tests
"""

import json
import pytest

from repoforge.graph_query import QueryResult, query_callers, query_callees, query_imports
from repoforge.symbols.graph import SymbolGraph, CallEdge
from repoforge.symbols.extractor import Symbol
from repoforge.graph import CodeGraph, Node, Edge


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def symbol_graph():
    """Build a small SymbolGraph for testing."""
    g = SymbolGraph()
    g.add_symbol(Symbol(
        name="main", kind="function", file="app.py", line=1, end_line=10,
    ))
    g.add_symbol(Symbol(
        name="helper", kind="function", file="app.py", line=12, end_line=20,
    ))
    g.add_symbol(Symbol(
        name="process", kind="function", file="lib.py", line=1, end_line=15,
    ))
    g.add_symbol(Symbol(
        name="helper", kind="function", file="lib.py", line=17, end_line=25,
    ))
    # main calls helper and process
    g.add_edge(CallEdge(caller="app.py::main", callee="app.py::helper"))
    g.add_edge(CallEdge(caller="app.py::main", callee="lib.py::process"))
    # process calls helper (in lib.py)
    g.add_edge(CallEdge(caller="lib.py::process", callee="lib.py::helper"))
    return g


@pytest.fixture
def code_graph():
    """Build a small CodeGraph for testing."""
    g = CodeGraph()
    g.add_node(Node(id="src/main.py", name="main", node_type="module", file_path="src/main.py"))
    g.add_node(Node(id="src/utils.py", name="utils", node_type="module", file_path="src/utils.py"))
    g.add_node(Node(id="src/db.py", name="db", node_type="module", file_path="src/db.py"))
    # main imports utils and db
    g.add_edge(Edge(source="src/main.py", target="src/utils.py", edge_type="imports"))
    g.add_edge(Edge(source="src/main.py", target="src/db.py", edge_type="imports"))
    # utils imports db
    g.add_edge(Edge(source="src/utils.py", target="src/db.py", edge_type="imports"))
    return g


# ---------------------------------------------------------------------------
# Tests: QueryResult
# ---------------------------------------------------------------------------


class TestQueryResult:
    def test_creation(self):
        r = QueryResult(
            query_type="callers",
            target="main",
            target_found=True,
            results=[{"name": "test"}],
            count=1,
        )
        assert r.query_type == "callers"
        assert r.target == "main"
        assert r.target_found is True
        assert r.count == 1

    def test_to_json_valid(self):
        r = QueryResult(
            query_type="callees",
            target="process",
            target_found=True,
            results=[{"name": "helper", "file": "lib.py"}],
            count=1,
        )
        data = json.loads(r.to_json())
        assert data["query"]["type"] == "callees"
        assert data["query"]["target"] == "process"
        assert data["target_found"] is True
        assert data["count"] == 1
        assert len(data["results"]) == 1

    def test_to_json_empty_results(self):
        r = QueryResult(
            query_type="callers",
            target="nonexistent",
            target_found=False,
        )
        data = json.loads(r.to_json())
        assert data["results"] == []
        assert data["count"] == 0
        assert data["target_found"] is False

    def test_to_json_consistent_schema(self):
        """All query types should produce the same top-level keys."""
        for qt in ("callers", "callees", "imports"):
            r = QueryResult(query_type=qt, target="x", target_found=False)
            data = json.loads(r.to_json())
            assert set(data.keys()) == {"query", "target_found", "results", "count"}
            assert set(data["query"].keys()) == {"type", "target"}


# ---------------------------------------------------------------------------
# Tests: query_callers
# ---------------------------------------------------------------------------


class TestQueryCallers:
    def test_known_symbol_with_callers(self, symbol_graph):
        result = query_callers(symbol_graph, "helper")
        assert result.target_found is True
        assert result.count >= 1
        caller_names = {r["name"] for r in result.results}
        # main calls app.py::helper, process calls lib.py::helper
        assert "main" in caller_names or "process" in caller_names

    def test_known_symbol_no_callers(self, symbol_graph):
        result = query_callers(symbol_graph, "main")
        assert result.target_found is True
        assert result.count == 0

    def test_unknown_symbol(self, symbol_graph):
        result = query_callers(symbol_graph, "nonexistent")
        assert result.target_found is False
        assert result.count == 0
        assert result.results == []

    def test_result_has_required_fields(self, symbol_graph):
        result = query_callers(symbol_graph, "process")
        assert result.target_found is True
        for r in result.results:
            assert "name" in r
            assert "file" in r
            assert "line" in r
            assert "kind" in r
            assert "id" in r

    def test_deduplicates_callers(self, symbol_graph):
        """Same caller should not appear twice even if multiple target matches."""
        result = query_callers(symbol_graph, "helper")
        ids = [r["id"] for r in result.results]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Tests: query_callees
# ---------------------------------------------------------------------------


class TestQueryCallees:
    def test_known_symbol_with_callees(self, symbol_graph):
        result = query_callees(symbol_graph, "main")
        assert result.target_found is True
        assert result.count >= 1
        callee_names = {r["name"] for r in result.results}
        assert "helper" in callee_names
        assert "process" in callee_names

    def test_known_symbol_no_callees(self, symbol_graph):
        result = query_callees(symbol_graph, "helper")
        # helper functions don't call anything in our fixture
        assert result.target_found is True
        assert result.count == 0

    def test_unknown_symbol(self, symbol_graph):
        result = query_callees(symbol_graph, "nonexistent")
        assert result.target_found is False
        assert result.count == 0

    def test_result_json_roundtrip(self, symbol_graph):
        result = query_callees(symbol_graph, "main")
        data = json.loads(result.to_json())
        assert data["query"]["type"] == "callees"
        assert data["query"]["target"] == "main"
        assert data["count"] == result.count


# ---------------------------------------------------------------------------
# Tests: query_imports
# ---------------------------------------------------------------------------


class TestQueryImports:
    def test_file_with_imports(self, code_graph):
        result = query_imports(code_graph, "src/main.py")
        assert result.target_found is True
        assert result.count == 2
        imported_files = {r["file"] for r in result.results}
        assert "src/utils.py" in imported_files
        assert "src/db.py" in imported_files

    def test_file_no_imports(self, code_graph):
        result = query_imports(code_graph, "src/db.py")
        assert result.target_found is True
        assert result.count == 0

    def test_file_not_found(self, code_graph):
        result = query_imports(code_graph, "nonexistent.py")
        assert result.target_found is False
        assert result.count == 0
        assert result.results == []

    def test_result_has_required_fields(self, code_graph):
        result = query_imports(code_graph, "src/main.py")
        for r in result.results:
            assert "file" in r
            assert "name" in r
            assert "id" in r

    def test_result_json_roundtrip(self, code_graph):
        result = query_imports(code_graph, "src/main.py")
        data = json.loads(result.to_json())
        assert data["query"]["type"] == "imports"
        assert data["query"]["target"] == "src/main.py"


# ---------------------------------------------------------------------------
# Tests: CLI integration
# ---------------------------------------------------------------------------


class TestCLIQuery:
    def test_query_help_shows_options(self):
        from click.testing import CliRunner
        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["graph", "--help"])
        assert result.exit_code == 0
        assert "--query" in result.output
        assert "--symbol" in result.output
        assert "--file" in result.output
        assert "callers" in result.output
        assert "callees" in result.output
        assert "imports" in result.output

    def test_query_callers_missing_symbol(self):
        from click.testing import CliRunner
        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["graph", "--query", "callers"])
        assert result.exit_code != 0

    def test_query_callees_missing_symbol(self):
        from click.testing import CliRunner
        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["graph", "--query", "callees"])
        assert result.exit_code != 0

    def test_query_imports_missing_file(self):
        from click.testing import CliRunner
        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["graph", "--query", "imports"])
        assert result.exit_code != 0

    def test_query_callers_real_repo(self):
        """Run callers query on the repoforge codebase itself."""
        from click.testing import CliRunner
        from repoforge.cli import main
        from pathlib import Path
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "graph", "-w", repo_dir,
            "--query", "callers", "--symbol", "build_graph", "-q",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["query"]["type"] == "callers"
        assert data["query"]["target"] == "build_graph"
        assert isinstance(data["results"], list)

    def test_query_callees_real_repo(self):
        from click.testing import CliRunner
        from repoforge.cli import main
        from pathlib import Path
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "graph", "-w", repo_dir,
            "--query", "callees", "--symbol", "build_graph", "-q",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["query"]["type"] == "callees"
        assert isinstance(data["results"], list)

    def test_query_imports_real_repo(self):
        from click.testing import CliRunner
        from repoforge.cli import main
        from pathlib import Path
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "graph", "-w", repo_dir,
            "--query", "imports", "--file", "repoforge/graph.py", "-q",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["query"]["type"] == "imports"
        assert data["query"]["target"] == "repoforge/graph.py"
        assert isinstance(data["results"], list)

    def test_query_nonexistent_symbol(self):
        from click.testing import CliRunner
        from repoforge.cli import main
        from pathlib import Path
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "graph", "-w", repo_dir,
            "--query", "callers", "--symbol", "totally_nonexistent_xyz", "-q",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["target_found"] is False
        assert data["results"] == []

    def test_query_output_to_file(self, tmp_path):
        from click.testing import CliRunner
        from repoforge.cli import main
        from pathlib import Path
        repo_dir = str(Path(__file__).parent.parent)
        output_file = str(tmp_path / "query.json")
        runner = CliRunner()
        result = runner.invoke(main, [
            "graph", "-w", repo_dir,
            "--query", "callers", "--symbol", "build_graph",
            "-o", output_file, "-q",
        ])
        assert result.exit_code == 0
        assert Path(output_file).exists()
        data = json.loads(Path(output_file).read_text(encoding="utf-8"))
        assert data["query"]["type"] == "callers"


# ---------------------------------------------------------------------------
# Tests: Public API exports
# ---------------------------------------------------------------------------


class TestPublicAPI:
    def test_imports_from_init(self):
        from repoforge import QueryResult, query_callers, query_callees, query_imports
        assert QueryResult is not None
        assert query_callers is not None
        assert query_callees is not None
        assert query_imports is not None

    def test_query_result_in_all(self):
        import repoforge
        assert "QueryResult" in repoforge.__all__
        assert "query_callers" in repoforge.__all__
        assert "query_callees" in repoforge.__all__
        assert "query_imports" in repoforge.__all__
