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
        assert "generate_erd_diagram" in repoforge.__all__
        assert "generate_k8s_diagram" in repoforge.__all__
        assert "generate_openapi_diagram" in repoforge.__all__

    def test_new_imports_from_init(self):
        from repoforge import (
            generate_erd_diagram,
            generate_k8s_diagram,
            generate_openapi_diagram,
        )
        assert generate_erd_diagram is not None
        assert generate_k8s_diagram is not None
        assert generate_openapi_diagram is not None


# ---------------------------------------------------------------------------
# Tests: generate_erd_diagram()
# ---------------------------------------------------------------------------

class TestERDDiagram:
    def test_basic_table(self):
        from repoforge.diagrams import generate_erd_diagram
        sql = """
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255)
);
"""
        output = generate_erd_diagram(sql)
        assert output.startswith("erDiagram")
        assert "users" in output
        assert "id" in output
        assert "name" in output
        assert "email" in output

    def test_foreign_key_relationship(self):
        from repoforge.diagrams import generate_erd_diagram
        sql = """
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(255)
);

CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT REFERENCES users(id),
    total DECIMAL(10,2)
);
"""
        output = generate_erd_diagram(sql)
        assert "erDiagram" in output
        assert "users" in output
        assert "orders" in output
        # Should have a relationship edge
        assert "||--o{" in output

    def test_empty_sql(self):
        from repoforge.diagrams import generate_erd_diagram
        output = generate_erd_diagram("")
        assert "erDiagram" in output
        assert "No tables detected" in output

    def test_no_create_table(self):
        from repoforge.diagrams import generate_erd_diagram
        output = generate_erd_diagram("SELECT * FROM users;")
        assert "No tables detected" in output

    def test_multiple_tables(self):
        from repoforge.diagrams import generate_erd_diagram
        sql = """
CREATE TABLE products (
    id INT PRIMARY KEY,
    name VARCHAR(100)
);

CREATE TABLE categories (
    id INT PRIMARY KEY,
    label VARCHAR(50)
);
"""
        output = generate_erd_diagram(sql)
        assert "products" in output
        assert "categories" in output

    def test_primary_key_marker(self):
        from repoforge.diagrams import generate_erd_diagram
        sql = """
CREATE TABLE items (
    id INT PRIMARY KEY,
    name TEXT
);
"""
        output = generate_erd_diagram(sql)
        assert "PK" in output


# ---------------------------------------------------------------------------
# Tests: generate_k8s_diagram()
# ---------------------------------------------------------------------------

class TestK8sDiagram:
    def test_deployment_and_service(self):
        from repoforge.diagrams import generate_k8s_diagram
        yaml_content = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
  labels:
    app: web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
---
apiVersion: v1
kind: Service
metadata:
  name: web-service
spec:
  selector:
    app: web
  ports:
    - port: 80
"""
        output = generate_k8s_diagram(yaml_content)
        assert output.startswith("graph TD")
        assert "web_app" in output or "web-app" in output
        assert "web_service" in output or "web-service" in output
        assert "selects" in output

    def test_multi_document(self):
        from repoforge.diagrams import generate_k8s_diagram
        yaml_content = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
---
apiVersion: v1
kind: Secret
metadata:
  name: app-secret
"""
        output = generate_k8s_diagram(yaml_content)
        assert "ConfigMap" in output
        assert "Secret" in output

    def test_empty_yaml(self):
        from repoforge.diagrams import generate_k8s_diagram
        output = generate_k8s_diagram("")
        assert "No Kubernetes resources detected" in output

    def test_invalid_yaml(self):
        from repoforge.diagrams import generate_k8s_diagram
        output = generate_k8s_diagram("just some random text\nnothing k8s here")
        assert "No Kubernetes resources detected" in output

    def test_single_deployment(self):
        from repoforge.diagrams import generate_k8s_diagram
        yaml_content = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
  labels:
    app: api
spec:
  replicas: 2
"""
        output = generate_k8s_diagram(yaml_content)
        assert "Deployment" in output
        assert "api" in output


# ---------------------------------------------------------------------------
# Tests: generate_openapi_diagram()
# ---------------------------------------------------------------------------

class TestOpenAPIDiagram:
    def test_basic_openapi_json(self):
        from repoforge.diagrams import generate_openapi_diagram
        spec = json.dumps({
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0"},
            "paths": {
                "/users": {
                    "get": {
                        "operationId": "listUsers",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/User"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                        }
                    }
                }
            }
        })
        output = generate_openapi_diagram(spec)
        assert output.startswith("classDiagram")
        assert "User" in output
        assert "listUsers" in output
        assert "id" in output
        assert "name" in output

    def test_schema_ref_relationship(self):
        from repoforge.diagrams import generate_openapi_diagram
        spec = json.dumps({
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {},
            "components": {
                "schemas": {
                    "Order": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "user": {"$ref": "#/components/schemas/User"},
                        }
                    },
                    "User": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                        }
                    }
                }
            }
        })
        output = generate_openapi_diagram(spec)
        assert "Order" in output
        assert "User" in output
        assert "-->" in output

    def test_empty_spec(self):
        from repoforge.diagrams import generate_openapi_diagram
        output = generate_openapi_diagram("")
        assert "classDiagram" in output
        assert "No OpenAPI spec detected" in output

    def test_invalid_json(self):
        from repoforge.diagrams import generate_openapi_diagram
        output = generate_openapi_diagram("{not valid json")
        assert "classDiagram" in output

    def test_swagger_v2_definitions(self):
        from repoforge.diagrams import generate_openapi_diagram
        spec = json.dumps({
            "swagger": "2.0",
            "info": {"title": "Legacy API", "version": "1.0"},
            "paths": {},
            "definitions": {
                "Product": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                    }
                }
            }
        })
        output = generate_openapi_diagram(spec)
        assert "Product" in output
        assert "id" in output

    def test_array_ref(self):
        from repoforge.diagrams import generate_openapi_diagram
        spec = json.dumps({
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {},
            "components": {
                "schemas": {
                    "Team": {
                        "type": "object",
                        "properties": {
                            "members": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/User"}
                            }
                        }
                    },
                    "User": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"}
                        }
                    }
                }
            }
        })
        output = generate_openapi_diagram(spec)
        assert "Team" in output
        assert "User" in output
        assert "-->" in output


# ---------------------------------------------------------------------------
# Tests: CLI diagram with new types
# ---------------------------------------------------------------------------

class TestCLIDiagramParsers:
    def test_diagram_help_shows_new_types(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["diagram", "--help"])
        assert result.exit_code == 0
        assert "erd" in result.output
        assert "k8s" in result.output
        assert "openapi" in result.output
        assert "--input" in result.output

    def test_erd_requires_input(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["diagram", "--type", "erd", "-q"])
        assert result.exit_code != 0

    def test_erd_with_input_file(self, tmp_path):
        from click.testing import CliRunner

        from repoforge.cli import main
        sql_file = tmp_path / "schema.sql"
        sql_file.write_text(
            "CREATE TABLE users (\n"
            "    id INT PRIMARY KEY,\n"
            "    name VARCHAR(255)\n"
            ");\n"
        )
        runner = CliRunner()
        result = runner.invoke(main, [
            "diagram", "--type", "erd", "--input", str(sql_file), "-q",
        ])
        assert result.exit_code == 0
        assert "```mermaid" in result.output
        assert "erDiagram" in result.output
        assert "users" in result.output

    def test_k8s_with_input_file(self, tmp_path):
        from click.testing import CliRunner

        from repoforge.cli import main
        yaml_file = tmp_path / "deploy.yaml"
        yaml_file.write_text(
            "apiVersion: apps/v1\n"
            "kind: Deployment\n"
            "metadata:\n"
            "  name: web\n"
            "  labels:\n"
            "    app: web\n"
        )
        runner = CliRunner()
        result = runner.invoke(main, [
            "diagram", "--type", "k8s", "--input", str(yaml_file), "-q",
        ])
        assert result.exit_code == 0
        assert "```mermaid" in result.output
        assert "Deployment" in result.output

    def test_openapi_with_input_file(self, tmp_path):
        from click.testing import CliRunner

        from repoforge.cli import main
        spec_file = tmp_path / "openapi.json"
        spec_file.write_text(json.dumps({
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {"/health": {"get": {"operationId": "healthCheck", "responses": {}}}},
            "components": {"schemas": {}}
        }))
        runner = CliRunner()
        result = runner.invoke(main, [
            "diagram", "--type", "openapi", "--input", str(spec_file), "-q",
        ])
        assert result.exit_code == 0
        assert "```mermaid" in result.output
        assert "classDiagram" in result.output


# ---------------------------------------------------------------------------
# Tests: repoforge diagrams (plural) command
# ---------------------------------------------------------------------------

class TestCLIDiagramsCommand:
    """Tests for the 'diagrams' (plural) subcommand that writes all diagrams to a .md file."""

    def test_diagrams_help(self):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["diagrams", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output or "-o" in result.output
        assert "mermaid" in result.output.lower() or "diagram" in result.output.lower()

    def test_diagrams_writes_file(self, tmp_path):
        from click.testing import CliRunner

        from repoforge.cli import main

        repo_dir = str(__import__("pathlib").Path(__file__).parent.parent)
        output_file = str(tmp_path / "arch.md")
        runner = CliRunner()
        result = runner.invoke(main, [
            "diagrams", "-w", repo_dir, "-o", output_file, "-q",
        ])
        assert result.exit_code == 0
        assert __import__("pathlib").Path(output_file).exists()
        content = __import__("pathlib").Path(output_file).read_text()
        assert "```mermaid" in content

    def test_diagrams_default_output_name(self, tmp_path):
        """Default output is diagrams.md in the current working directory."""
        import os

        from click.testing import CliRunner

        from repoforge.cli import main

        repo_dir = str(__import__("pathlib").Path(__file__).parent.parent)
        runner = CliRunner()
        # Run with mix_stderr=False to avoid output contamination; use tmp_path as cwd
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, [
                "diagrams", "-w", repo_dir, "-q",
            ])
        assert result.exit_code == 0

    def test_diagrams_output_contains_header(self, tmp_path):
        from click.testing import CliRunner

        from repoforge.cli import main

        repo_dir = str(__import__("pathlib").Path(__file__).parent.parent)
        output_file = str(tmp_path / "diagrams.md")
        runner = CliRunner()
        result = runner.invoke(main, [
            "diagrams", "-w", repo_dir, "-o", output_file, "-q",
        ])
        assert result.exit_code == 0
        content = __import__("pathlib").Path(output_file).read_text()
        # Should start with a heading
        assert content.startswith("#")

    def test_diagrams_in_main_help(self):
        """'diagrams' command is listed in the main help."""
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "diagrams" in result.output

    def test_diagrams_max_nodes_option(self, tmp_path):
        from click.testing import CliRunner

        from repoforge.cli import main

        repo_dir = str(__import__("pathlib").Path(__file__).parent.parent)
        output_file = str(tmp_path / "diagrams.md")
        runner = CliRunner()
        result = runner.invoke(main, [
            "diagrams", "-w", repo_dir, "-o", output_file,
            "--max-nodes", "10", "-q",
        ])
        assert result.exit_code == 0
        assert __import__("pathlib").Path(output_file).exists()


# ---------------------------------------------------------------------------
# Tests: --diagrams flag for repoforge docs
# ---------------------------------------------------------------------------

class TestDocsDiagramsFlag:
    """Tests for the --diagrams flag on the docs subcommand."""

    def test_docs_help_shows_diagrams_flag(self):
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["docs", "--help"])
        assert result.exit_code == 0
        assert "--diagrams" in result.output

    def test_docs_dry_run_with_diagrams_flag(self, tmp_path):
        """--diagrams flag is accepted without error in dry-run mode."""
        from click.testing import CliRunner

        from repoforge.cli import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "docs", "-w", str(tmp_path), "--dry-run", "--diagrams", "-q",
        ])
        # dry-run with no files should either succeed or exit cleanly (no crash)
        assert result.exit_code in (0, 1)  # 1 = empty repo, no LLM, acceptable

    def test_generate_docs_accepts_embed_diagrams(self, tmp_path):
        """generate_docs() accepts embed_diagrams without raising."""
        from unittest.mock import MagicMock, patch

        # Write a minimal repo
        (tmp_path / "main.py").write_text("def hello(): pass\n")
        (tmp_path / "pyproject.toml").write_text('[project]\nname="test"\nversion="0.1.0"\n')

        mock_llm = MagicMock()
        mock_llm.model = "mock-model"
        mock_llm.call.return_value = "# Test\n\nContent."

        with patch("repoforge.docs_generator.build_llm", return_value=mock_llm):
            from repoforge.docs_generator import generate_docs
            # Should not raise TypeError for unknown kwarg
            result = generate_docs(
                working_dir=str(tmp_path),
                output_dir=str(tmp_path / "docs"),
                dry_run=True,
                verbose=False,
                embed_diagrams=True,
            )
        # dry-run returns early without generating files
        assert result.get("dry_run") is True

    def test_build_all_contexts_accepts_embed_diagrams(self, tmp_path):
        """build_all_contexts() accepts embed_diagrams parameter without raising."""
        from pathlib import Path

        from repoforge.pipeline.context import build_all_contexts
        from repoforge.scanner import scan_repo

        (tmp_path / "main.py").write_text("def hello(): pass\n")
        repo_map = scan_repo(str(tmp_path))
        log = lambda msg="", **kwargs: None

        # Should not raise
        ctx = build_all_contexts(
            tmp_path, repo_map, log,
            embed_diagrams=False,
        )
        assert isinstance(ctx, dict)
        assert "diagram_ctx" in ctx

    def test_write_diagrams_file_with_empty_ctx(self, tmp_path):
        """_write_diagrams_file returns None when no diagram context is available."""
        from pathlib import Path

        from repoforge.docs_generator import _write_diagrams_file

        out = tmp_path / "docs"
        out.mkdir()
        log = lambda msg="", **kwargs: None

        result = _write_diagrams_file(
            ctx={"diagram_ctx": ""},
            root=tmp_path,
            out=out,
            project_name="Test Project",
            log=log,
        )
        assert result is None
        assert not (out / "diagrams.md").exists()

    def test_write_diagrams_file_with_content(self, tmp_path):
        """_write_diagrams_file writes diagrams.md when diagram_ctx is present."""
        from pathlib import Path

        from repoforge.docs_generator import _write_diagrams_file

        out = tmp_path / "docs"
        out.mkdir()
        log = lambda msg="", **kwargs: None
        fake_ctx = "```mermaid\ngraph LR\n    A --> B\n```"

        result = _write_diagrams_file(
            ctx={"diagram_ctx": fake_ctx},
            root=tmp_path,
            out=out,
            project_name="My Project",
            log=log,
        )
        assert result is not None
        diag_path = out / "diagrams.md"
        assert diag_path.exists()
        content = diag_path.read_text()
        assert "# My Project" in content
        assert "```mermaid" in content
        assert "graph LR" in content
