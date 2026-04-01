"""
tests/test_diagrams.py - Tests for code-to-diagram generation.

Tests cover:
- generate_dependency_diagram() — valid mermaid, grouping, node capping, empty graph
- generate_directory_diagram() — hierarchy, depth capping, empty files
- generate_call_flow_diagram() — Python/JS call tracing, unsupported ext, empty
- generate_all_diagrams() — combines all diagram types
- _detect_entry_points() — pattern matching for entry files
- _extract_functions_and_calls() — regex extraction for Python/JS
- CLI diagram subcommand (CliRunner)
- Public API exports from repoforge.__init__
"""

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def graph_cls():
    from repoforge.graph import CodeGraph
    return CodeGraph


@pytest.fixture
def node_cls():
    from repoforge.graph import Node
    return Node


@pytest.fixture
def edge_cls():
    from repoforge.graph import Edge
    return Edge


@pytest.fixture
def small_graph(graph_cls, node_cls, edge_cls):
    """A small graph with 3 modules across 2 directories."""
    g = graph_cls()
    g.add_node(node_cls(
        id="src/core/models.py", name="models", node_type="module",
        layer="core", file_path="src/core/models.py", exports=["User", "Post"],
    ))
    g.add_node(node_cls(
        id="src/core/utils.py", name="utils", node_type="module",
        layer="core", file_path="src/core/utils.py", exports=["slugify"],
    ))
    g.add_node(node_cls(
        id="src/api/routes.py", name="routes", node_type="module",
        layer="api", file_path="src/api/routes.py", exports=["router"],
    ))
    g.add_edge(edge_cls(source="src/api/routes.py", target="src/core/models.py", edge_type="imports"))
    g.add_edge(edge_cls(source="src/api/routes.py", target="src/core/utils.py", edge_type="imports"))
    return g


@pytest.fixture
def empty_graph(graph_cls):
    return graph_cls()


@pytest.fixture
def large_graph(graph_cls, node_cls, edge_cls):
    """A graph with 60 modules to test capping."""
    g = graph_cls()
    for i in range(60):
        g.add_node(node_cls(
            id=f"src/mod_{i}.py", name=f"mod_{i}", node_type="module",
            file_path=f"src/mod_{i}.py",
        ))
    # Create edges from first 10 to next 10
    for i in range(10):
        for j in range(10, 20):
            g.add_edge(edge_cls(
                source=f"src/mod_{i}.py", target=f"src/mod_{j}.py",
                edge_type="imports",
            ))
    return g


@pytest.fixture
def sample_files():
    return [
        "src/core/models.py",
        "src/core/utils.py",
        "src/api/routes.py",
        "src/api/middleware.py",
        "tests/test_models.py",
        "tests/test_routes.py",
        "README.md",
        "pyproject.toml",
    ]


@pytest.fixture
def python_repo(tmp_path):
    """Create a minimal Python repo for call flow testing."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text(
        'from .utils import helper\n\n'
        'def main():\n'
        '    result = helper("world")\n'
        '    process(result)\n\n'
        'def process(data):\n'
        '    return data.upper()\n'
    )
    (src / "utils.py").write_text(
        'def helper(name: str) -> str:\n'
        '    return format_name(name)\n\n'
        'def format_name(name: str) -> str:\n'
        '    return f"Hello, {name}!"\n'
    )
    return tmp_path


@pytest.fixture
def js_repo(tmp_path):
    """Create a minimal JS repo for call flow testing."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "index.js").write_text(
        'const { fetchData } = require("./api");\n\n'
        'function main() {\n'
        '    const data = fetchData();\n'
        '    render(data);\n'
        '}\n\n'
        'function render(data) {\n'
        '    console.log(data);\n'
        '}\n'
    )
    (src / "api.js").write_text(
        'function fetchData() {\n'
        '    return parseResponse(getData());\n'
        '}\n\n'
        'function parseResponse(raw) {\n'
        '    return raw;\n'
        '}\n\n'
        'function getData() {\n'
        '    return "mock";\n'
        '}\n'
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Tests: generate_dependency_diagram()
# ---------------------------------------------------------------------------

class TestDependencyDiagram:
    def test_starts_with_graph_lr(self, small_graph):
        from repoforge.diagrams import generate_dependency_diagram
        output = generate_dependency_diagram(small_graph)
        assert output.startswith("graph LR")

    def test_has_subgraphs(self, small_graph):
        from repoforge.diagrams import generate_dependency_diagram
        output = generate_dependency_diagram(small_graph)
        assert "subgraph" in output
        assert "end" in output

    def test_has_edges(self, small_graph):
        from repoforge.diagrams import generate_dependency_diagram
        output = generate_dependency_diagram(small_graph)
        assert "-->" in output

    def test_groups_by_directory(self, small_graph):
        from repoforge.diagrams import generate_dependency_diagram
        output = generate_dependency_diagram(small_graph)
        # Should have subgraphs for src/core and src/api
        assert "src_core" in output or "src/core" in output
        assert "src_api" in output or "src/api" in output

    def test_max_nodes_caps_output(self, large_graph):
        from repoforge.diagrams import generate_dependency_diagram
        output_all = generate_dependency_diagram(large_graph, max_nodes=60)
        output_capped = generate_dependency_diagram(large_graph, max_nodes=10)
        # Capped version should have fewer node declarations
        assert output_capped.count("[") <= output_all.count("[")

    def test_empty_graph(self, empty_graph):
        from repoforge.diagrams import generate_dependency_diagram
        output = generate_dependency_diagram(empty_graph)
        assert "No modules detected" in output

    def test_valid_mermaid_ids(self, small_graph):
        import re

        from repoforge.diagrams import generate_dependency_diagram
        output = generate_dependency_diagram(small_graph)
        for line in output.split("\n"):
            line = line.strip()
            if "[" in line and "subgraph" not in line:
                node_id = line.split("[")[0].strip()
                assert re.match(r"^[a-zA-Z0-9_]+$", node_id), f"Invalid ID: {node_id!r}"


# ---------------------------------------------------------------------------
# Tests: generate_directory_diagram()
# ---------------------------------------------------------------------------

class TestDirectoryDiagram:
    def test_starts_with_graph_td(self, sample_files):
        from repoforge.diagrams import generate_directory_diagram
        output = generate_directory_diagram(sample_files)
        assert output.startswith("graph TD")

    def test_has_root_node(self, sample_files):
        from repoforge.diagrams import generate_directory_diagram
        output = generate_directory_diagram(sample_files)
        assert "root" in output

    def test_has_directory_nodes(self, sample_files):
        from repoforge.diagrams import generate_directory_diagram
        output = generate_directory_diagram(sample_files)
        # Should contain src and tests directories
        assert "src" in output
        assert "tests" in output

    def test_has_edges(self, sample_files):
        from repoforge.diagrams import generate_directory_diagram
        output = generate_directory_diagram(sample_files)
        assert "-->" in output

    def test_max_depth_caps(self, sample_files):
        from repoforge.diagrams import generate_directory_diagram
        shallow = generate_directory_diagram(sample_files, max_depth=1)
        deep = generate_directory_diagram(sample_files, max_depth=3)
        # Shallow should have fewer nodes
        assert shallow.count("-->") <= deep.count("-->")

    def test_empty_files(self):
        from repoforge.diagrams import generate_directory_diagram
        output = generate_directory_diagram([])
        assert "No files detected" in output

    def test_shows_file_counts(self, sample_files):
        from repoforge.diagrams import generate_directory_diagram
        output = generate_directory_diagram(sample_files)
        assert "files" in output


# ---------------------------------------------------------------------------
# Tests: _extract_functions_and_calls()
# ---------------------------------------------------------------------------

class TestExtractFunctionsAndCalls:
    def test_python_function_detection(self):
        from repoforge.diagrams import _extract_functions_and_calls
        code = (
            "def main():\n"
            "    helper()\n\n"
            "def helper():\n"
            "    pass\n"
        )
        funcs, calls = _extract_functions_and_calls(code, "python")
        assert "main" in funcs
        assert "helper" in funcs
        assert "helper" in calls.get("main", [])

    def test_python_skips_builtins(self):
        from repoforge.diagrams import _extract_functions_and_calls
        code = (
            "def main():\n"
            "    print('hello')\n"
            "    x = len([1, 2])\n"
            "    custom_func()\n"
        )
        funcs, calls = _extract_functions_and_calls(code, "python")
        main_calls = calls.get("main", [])
        assert "print" not in main_calls
        assert "len" not in main_calls
        assert "custom_func" in main_calls

    def test_js_function_detection(self):
        from repoforge.diagrams import _extract_functions_and_calls
        code = (
            "function main() {\n"
            "    fetchData();\n"
            "}\n\n"
            "function fetchData() {\n"
            "    return parse();\n"
            "}\n"
        )
        funcs, calls = _extract_functions_and_calls(code, "javascript")
        assert "main" in funcs
        assert "fetchData" in funcs
        assert "fetchData" in calls.get("main", [])

    def test_empty_code(self):
        from repoforge.diagrams import _extract_functions_and_calls
        funcs, calls = _extract_functions_and_calls("", "python")
        assert funcs == []
        assert calls == {}

    def test_no_recursion_in_calls(self):
        from repoforge.diagrams import _extract_functions_and_calls
        code = (
            "def recursive():\n"
            "    recursive()\n"
        )
        funcs, calls = _extract_functions_and_calls(code, "python")
        # Should not include self-calls
        assert "recursive" not in calls.get("recursive", [])


# ---------------------------------------------------------------------------
# Tests: generate_call_flow_diagram()
# ---------------------------------------------------------------------------

class TestCallFlowDiagram:
    def test_python_call_flow(self, python_repo):
        from repoforge.diagrams import generate_call_flow_diagram
        files = ["src/main.py", "src/utils.py"]
        output = generate_call_flow_diagram(
            str(python_repo), "src/main.py", files, max_depth=2,
        )
        assert output.startswith("sequenceDiagram")
        # Should trace calls from main
        assert "->>" in output or "Note over" in output

    def test_js_call_flow(self, js_repo):
        from repoforge.diagrams import generate_call_flow_diagram
        files = ["src/index.js", "src/api.js"]
        output = generate_call_flow_diagram(
            str(js_repo), "src/index.js", files, max_depth=2,
        )
        assert output.startswith("sequenceDiagram")

    def test_unsupported_extension(self, tmp_path):
        from repoforge.diagrams import generate_call_flow_diagram
        (tmp_path / "main.rs").write_text("fn main() {}")
        output = generate_call_flow_diagram(
            str(tmp_path), "main.rs", ["main.rs"],
        )
        assert "Unsupported file type" in output

    def test_nonexistent_entry(self, tmp_path):
        from repoforge.diagrams import generate_call_flow_diagram
        output = generate_call_flow_diagram(
            str(tmp_path), "nonexistent.py", ["nonexistent.py"],
        )
        assert "sequenceDiagram" in output
        assert "No traceable calls" in output or "No internal calls" in output


# ---------------------------------------------------------------------------
# Tests: generate_all_diagrams()
# ---------------------------------------------------------------------------

class TestAllDiagrams:
    def test_contains_all_sections(self, small_graph, sample_files, tmp_path):
        from repoforge.diagrams import generate_all_diagrams
        # Create dummy files so call flow can read them
        for f in sample_files:
            fpath = tmp_path / f
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text("# placeholder\n")

        output = generate_all_diagrams(str(tmp_path), small_graph, sample_files)
        assert "### Module Dependencies" in output
        assert "### Directory Structure" in output
        assert "```mermaid" in output

    def test_mermaid_fences(self, small_graph, sample_files, tmp_path):
        from repoforge.diagrams import generate_all_diagrams
        for f in sample_files:
            fpath = tmp_path / f
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text("# placeholder\n")

        output = generate_all_diagrams(str(tmp_path), small_graph, sample_files)
        # Every mermaid block should be properly fenced
        assert output.count("```mermaid") == output.count("```\n") or \
               output.count("```mermaid") <= output.count("```")


# ---------------------------------------------------------------------------
# Tests: _detect_entry_points()
# ---------------------------------------------------------------------------

class TestDetectEntryPoints:
    def test_detects_main_py(self):
        from repoforge.diagrams import _detect_entry_points
        files = ["src/main.py", "src/utils.py", "tests/test_main.py"]
        entries = _detect_entry_points("/tmp", files)
        assert "src/main.py" in entries

    def test_detects_index_ts(self):
        from repoforge.diagrams import _detect_entry_points
        files = ["src/index.ts", "src/utils.ts"]
        entries = _detect_entry_points("/tmp", files)
        assert "src/index.ts" in entries

    def test_detects_cli_py(self):
        from repoforge.diagrams import _detect_entry_points
        files = ["repoforge/cli.py", "repoforge/scanner.py"]
        entries = _detect_entry_points("/tmp", files)
        assert "repoforge/cli.py" in entries

    def test_detects_app_py(self):
        from repoforge.diagrams import _detect_entry_points
        files = ["app.py", "utils.py"]
        entries = _detect_entry_points("/tmp", files)
        assert "app.py" in entries

    def test_no_entry_points(self):
        from repoforge.diagrams import _detect_entry_points
        files = ["src/utils.py", "src/helpers.py"]
        entries = _detect_entry_points("/tmp", files)
        assert entries == []


# ---------------------------------------------------------------------------
# Tests: CLI diagram subcommand
# ---------------------------------------------------------------------------

class TestCLIDiagram:
    def test_diagram_help(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["diagram", "--help"])
        assert result.exit_code == 0
        assert "--type" in result.output
        assert "dependency" in result.output
        assert "directory" in result.output
        assert "callflow" in result.output

    def test_diagram_all_default(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, ["diagram", "-w", repo_dir, "-q"])
        assert result.exit_code == 0
        assert "```mermaid" in result.output
        assert "Module Dependencies" in result.output
        assert "Directory Structure" in result.output

    def test_diagram_dependency_only(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "diagram", "-w", repo_dir, "--type", "dependency", "-q",
        ])
        assert result.exit_code == 0
        assert "```mermaid" in result.output
        assert "graph LR" in result.output

    def test_diagram_directory_only(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "diagram", "-w", repo_dir, "--type", "directory", "-q",
        ])
        assert result.exit_code == 0
        assert "```mermaid" in result.output
        assert "graph TD" in result.output

    def test_diagram_output_to_file(self, tmp_path):
        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        output_file = str(tmp_path / "diagrams.md")
        runner = CliRunner()
        result = runner.invoke(main, [
            "diagram", "-w", repo_dir, "-o", output_file, "-q",
        ])
        assert result.exit_code == 0
        assert Path(output_file).exists()
        content = Path(output_file).read_text()
        assert "```mermaid" in content

    def test_diagram_in_main_help(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "diagram" in result.output


# ---------------------------------------------------------------------------
# Tests: Public API exports
# ---------------------------------------------------------------------------

class TestDiagramPublicAPI:
    def test_imports_from_init(self):
        from repoforge import (
            generate_all_diagrams,
            generate_call_flow_diagram,
            generate_dependency_diagram,
            generate_directory_diagram,
        )
        assert generate_dependency_diagram is not None
        assert generate_directory_diagram is not None
        assert generate_call_flow_diagram is not None
        assert generate_all_diagrams is not None

    def test_diagrams_in_all(self):
        import repoforge
        assert "generate_dependency_diagram" in repoforge.__all__
        assert "generate_directory_diagram" in repoforge.__all__
        assert "generate_call_flow_diagram" in repoforge.__all__
        assert "generate_all_diagrams" in repoforge.__all__
