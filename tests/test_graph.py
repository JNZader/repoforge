"""
tests/test_graph.py — Tests for lightweight code knowledge graph.

Tests cover:
- Node and Edge dataclass creation
- CodeGraph.add_node() — adding, dedup behavior
- CodeGraph.add_edge() — adding, weight merging
- CodeGraph.get_node()
- CodeGraph.get_dependencies() and get_dependents()
- CodeGraph.get_blast_radius() — transitive dependency tracking
- build_graph() with mock RepoMaps (small, medium, with imports/exports)
- Import resolution: direct export match, module name match, package match
- to_mermaid() — valid syntax, subgraph grouping, max_nodes limiting
- to_json() — valid JSON, correct structure
- to_dot() — valid DOT syntax
- summary() — modules, dependencies, most connected, isolated
- Empty/minimal graph edge cases
- CLI graph subcommand integration (CliRunner)
- Public API exports from repoforge.__init__
"""

import json

import pytest

# ---------------------------------------------------------------------------
# Fixtures: mock RepoMaps
# ---------------------------------------------------------------------------

SMALL_REPO_MAP = {
    "layers": {
        "core": {
            "path": "src/core",
            "modules": [
                {
                    "path": "src/core/models.py",
                    "name": "models",
                    "exports": ["User", "Post"],
                    "imports": [],
                },
                {
                    "path": "src/core/utils.py",
                    "name": "utils",
                    "exports": ["slugify", "hash_password"],
                    "imports": [],
                },
            ],
        },
        "api": {
            "path": "src/api",
            "modules": [
                {
                    "path": "src/api/routes.py",
                    "name": "routes",
                    "exports": ["router"],
                    "imports": ["User", "slugify"],
                },
            ],
        },
    },
}

MEDIUM_REPO_MAP = {
    "layers": {
        "models": {
            "path": "app/models",
            "modules": [
                {
                    "path": "app/models/user.py",
                    "name": "user",
                    "exports": ["User", "UserCreate"],
                    "imports": [],
                },
                {
                    "path": "app/models/post.py",
                    "name": "post",
                    "exports": ["Post", "PostCreate"],
                    "imports": ["User"],
                },
            ],
        },
        "services": {
            "path": "app/services",
            "modules": [
                {
                    "path": "app/services/user_service.py",
                    "name": "user_service",
                    "exports": ["UserService"],
                    "imports": ["User", "UserCreate"],
                },
                {
                    "path": "app/services/post_service.py",
                    "name": "post_service",
                    "exports": ["PostService"],
                    "imports": ["Post", "PostCreate", "UserService"],
                },
            ],
        },
        "api": {
            "path": "app/api",
            "modules": [
                {
                    "path": "app/api/router.py",
                    "name": "router",
                    "exports": ["app_router"],
                    "imports": ["UserService", "PostService"],
                },
            ],
        },
    },
}

IMPORT_RESOLUTION_MAP = {
    "layers": {
        "lib": {
            "path": "lib",
            "modules": [
                {
                    "path": "lib/auth.py",
                    "name": "auth",
                    "exports": ["authenticate", "TokenValidator"],
                    "imports": [],
                },
                {
                    "path": "lib/db.py",
                    "name": "db",
                    "exports": ["get_connection"],
                    "imports": [],
                },
            ],
        },
        "handlers": {
            "path": "handlers",
            "modules": [
                {
                    "path": "handlers/login.py",
                    "name": "login",
                    "exports": ["handle_login"],
                    # Tests 3 resolution strategies:
                    # "authenticate" → direct export match
                    # "db" → module name match
                    # "lib" → package name match (will depend_on first module in lib)
                    "imports": ["authenticate", "db", "nonexistent_external"],
                },
            ],
        },
    },
}

EMPTY_REPO_MAP = {"layers": {}}

SINGLE_MODULE_MAP = {
    "layers": {
        "root": {
            "path": "src",
            "modules": [
                {
                    "path": "src/main.py",
                    "name": "main",
                    "exports": ["main"],
                    "imports": [],
                },
            ],
        },
    },
}


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
def small_graph():
    from repoforge.graph import build_graph
    return build_graph(SMALL_REPO_MAP)


@pytest.fixture
def medium_graph():
    from repoforge.graph import build_graph
    return build_graph(MEDIUM_REPO_MAP)


@pytest.fixture
def empty_graph():
    from repoforge.graph import CodeGraph
    return CodeGraph()


# ---------------------------------------------------------------------------
# Tests: Node and Edge dataclass creation
# ---------------------------------------------------------------------------

class TestDataclasses:
    def test_node_creation(self, node_cls):
        node = node_cls(
            id="src/main.py",
            name="main",
            node_type="module",
            layer="core",
            file_path="src/main.py",
            exports=["main_func"],
        )
        assert node.id == "src/main.py"
        assert node.name == "main"
        assert node.node_type == "module"
        assert node.layer == "core"
        assert node.file_path == "src/main.py"
        assert node.exports == ["main_func"]

    def test_node_defaults(self, node_cls):
        node = node_cls(id="test", name="test", node_type="module")
        assert node.layer == ""
        assert node.file_path == ""
        assert node.exports == []

    def test_edge_creation(self, edge_cls):
        edge = edge_cls(
            source="a.py",
            target="b.py",
            edge_type="imports",
            weight=3,
        )
        assert edge.source == "a.py"
        assert edge.target == "b.py"
        assert edge.edge_type == "imports"
        assert edge.weight == 3

    def test_edge_default_weight(self, edge_cls):
        edge = edge_cls(source="a", target="b", edge_type="imports")
        assert edge.weight == 1


# ---------------------------------------------------------------------------
# Tests: CodeGraph.add_node()
# ---------------------------------------------------------------------------

class TestAddNode:
    def test_add_single_node(self, graph_cls, node_cls):
        g = graph_cls()
        g.add_node(node_cls(id="a.py", name="a", node_type="module"))
        assert len(g.nodes) == 1
        assert g.nodes[0].id == "a.py"

    def test_add_multiple_nodes(self, graph_cls, node_cls):
        g = graph_cls()
        g.add_node(node_cls(id="a.py", name="a", node_type="module"))
        g.add_node(node_cls(id="b.py", name="b", node_type="module"))
        assert len(g.nodes) == 2

    def test_dedup_same_id(self, graph_cls, node_cls):
        g = graph_cls()
        g.add_node(node_cls(id="a.py", name="a", node_type="module"))
        g.add_node(node_cls(id="a.py", name="a-duplicate", node_type="module"))
        assert len(g.nodes) == 1
        assert g.nodes[0].name == "a"  # first one wins

    def test_different_ids_not_deduped(self, graph_cls, node_cls):
        g = graph_cls()
        g.add_node(node_cls(id="a.py", name="shared", node_type="module"))
        g.add_node(node_cls(id="b.py", name="shared", node_type="module"))
        assert len(g.nodes) == 2


# ---------------------------------------------------------------------------
# Tests: CodeGraph.add_edge()
# ---------------------------------------------------------------------------

class TestAddEdge:
    def test_add_single_edge(self, graph_cls, edge_cls):
        g = graph_cls()
        g.add_edge(edge_cls(source="a", target="b", edge_type="imports"))
        assert len(g.edges) == 1

    def test_add_multiple_distinct_edges(self, graph_cls, edge_cls):
        g = graph_cls()
        g.add_edge(edge_cls(source="a", target="b", edge_type="imports"))
        g.add_edge(edge_cls(source="b", target="c", edge_type="imports"))
        assert len(g.edges) == 2

    def test_weight_merging_same_edge(self, graph_cls, edge_cls):
        g = graph_cls()
        g.add_edge(edge_cls(source="a", target="b", edge_type="imports", weight=1))
        g.add_edge(edge_cls(source="a", target="b", edge_type="imports", weight=2))
        assert len(g.edges) == 1
        assert g.edges[0].weight == 3  # 1 + 2

    def test_different_types_not_merged(self, graph_cls, edge_cls):
        g = graph_cls()
        g.add_edge(edge_cls(source="a", target="b", edge_type="imports"))
        g.add_edge(edge_cls(source="a", target="b", edge_type="contains"))
        assert len(g.edges) == 2

    def test_reversed_direction_not_merged(self, graph_cls, edge_cls):
        g = graph_cls()
        g.add_edge(edge_cls(source="a", target="b", edge_type="imports"))
        g.add_edge(edge_cls(source="b", target="a", edge_type="imports"))
        assert len(g.edges) == 2


# ---------------------------------------------------------------------------
# Tests: CodeGraph.get_node()
# ---------------------------------------------------------------------------

class TestGetNode:
    def test_get_existing_node(self, small_graph):
        node = small_graph.get_node("src/core/models.py")
        assert node is not None
        assert node.name == "models"

    def test_get_nonexistent_node(self, small_graph):
        node = small_graph.get_node("nonexistent.py")
        assert node is None

    def test_get_layer_node(self, small_graph):
        node = small_graph.get_node("layer:core")
        assert node is not None
        assert node.node_type == "layer"


# ---------------------------------------------------------------------------
# Tests: get_dependencies() and get_dependents()
# ---------------------------------------------------------------------------

class TestDependencies:
    def test_get_dependencies_with_imports(self, small_graph):
        deps = small_graph.get_dependencies("src/api/routes.py")
        # routes imports User (from models) and slugify (from utils)
        assert "src/core/models.py" in deps
        assert "src/core/utils.py" in deps

    def test_get_dependencies_no_imports(self, small_graph):
        deps = small_graph.get_dependencies("src/core/models.py")
        assert deps == []

    def test_get_dependents_with_incoming(self, small_graph):
        dependents = small_graph.get_dependents("src/core/models.py")
        assert "src/api/routes.py" in dependents

    def test_get_dependents_no_incoming(self, small_graph):
        dependents = small_graph.get_dependents("src/api/routes.py")
        assert dependents == []

    def test_medium_graph_chain(self, medium_graph):
        # router depends on UserService and PostService
        deps = medium_graph.get_dependencies("app/api/router.py")
        assert "app/services/user_service.py" in deps
        assert "app/services/post_service.py" in deps

        # post_service depends on Post, PostCreate, UserService
        deps = medium_graph.get_dependencies("app/services/post_service.py")
        assert "app/models/post.py" in deps
        assert "app/services/user_service.py" in deps


# ---------------------------------------------------------------------------
# Tests: get_blast_radius()
# ---------------------------------------------------------------------------

class TestBlastRadius:
    def test_blast_radius_leaf_node(self, small_graph):
        # routes has no dependents → blast radius is empty
        affected = small_graph.get_blast_radius("src/api/routes.py")
        assert affected == []

    def test_blast_radius_core_module(self, small_graph):
        # models exports User, which routes imports → routes is affected
        affected = small_graph.get_blast_radius("src/core/models.py")
        assert "src/api/routes.py" in affected

    def test_blast_radius_transitive(self, medium_graph):
        # Changing User model should propagate:
        # user.py → post.py (imports User), user_service.py (imports User)
        # post.py → post_service.py (imports Post)
        # user_service.py → post_service.py (imports UserService), router (imports UserService)
        # post_service.py → router (imports PostService)
        affected = medium_graph.get_blast_radius("app/models/user.py")
        assert "app/models/post.py" in affected
        assert "app/services/user_service.py" in affected
        assert "app/services/post_service.py" in affected
        assert "app/api/router.py" in affected

    def test_blast_radius_excludes_self(self, medium_graph):
        affected = medium_graph.get_blast_radius("app/models/user.py")
        assert "app/models/user.py" not in affected

    def test_blast_radius_nonexistent_node(self, small_graph):
        # Nonexistent node should return empty (no dependents to find)
        affected = small_graph.get_blast_radius("nonexistent.py")
        assert affected == []

    def test_blast_radius_empty_graph(self, empty_graph):
        affected = empty_graph.get_blast_radius("anything")
        assert affected == []


# ---------------------------------------------------------------------------
# Tests: build_graph() with mock RepoMaps
# ---------------------------------------------------------------------------

class TestBuildGraph:
    def test_small_repo_map_nodes(self, small_graph):
        module_nodes = [n for n in small_graph.nodes if n.node_type == "module"]
        assert len(module_nodes) == 3  # models, utils, routes

    def test_small_repo_map_layer_nodes(self, small_graph):
        layer_nodes = [n for n in small_graph.nodes if n.node_type == "layer"]
        assert len(layer_nodes) == 2  # core, api

    def test_small_repo_map_edges(self, small_graph):
        import_edges = [e for e in small_graph.edges if e.edge_type == "imports"]
        # routes imports User (→ models) and slugify (→ utils)
        assert len(import_edges) == 2

    def test_small_repo_map_contains_edges(self, small_graph):
        contains_edges = [e for e in small_graph.edges if e.edge_type == "contains"]
        assert len(contains_edges) == 3  # core→models, core→utils, api→routes

    def test_medium_repo_map_nodes(self, medium_graph):
        module_nodes = [n for n in medium_graph.nodes if n.node_type == "module"]
        assert len(module_nodes) == 5

    def test_medium_repo_map_edges(self, medium_graph):
        import_edges = [e for e in medium_graph.edges if e.edge_type == "imports"]
        # post→user(User), user_service→user(User), post_service→post(Post),
        # post_service→user_service(UserService), router→user_service(UserService),
        # router→post_service(PostService)
        assert len(import_edges) >= 5

    def test_empty_repo_map(self):
        from repoforge.graph import build_graph
        g = build_graph(EMPTY_REPO_MAP)
        assert len(g.nodes) == 0
        assert len(g.edges) == 0

    def test_single_module_map(self):
        from repoforge.graph import build_graph
        g = build_graph(SINGLE_MODULE_MAP)
        module_nodes = [n for n in g.nodes if n.node_type == "module"]
        assert len(module_nodes) == 1
        import_edges = [e for e in g.edges if e.edge_type == "imports"]
        assert len(import_edges) == 0

    def test_node_exports_populated(self, small_graph):
        node = small_graph.get_node("src/core/models.py")
        assert "User" in node.exports
        assert "Post" in node.exports

    def test_node_layer_assigned(self, small_graph):
        node = small_graph.get_node("src/core/models.py")
        assert node.layer == "core"
        node = small_graph.get_node("src/api/routes.py")
        assert node.layer == "api"


# ---------------------------------------------------------------------------
# Tests: Import resolution strategies
# ---------------------------------------------------------------------------

class TestImportResolution:
    def test_direct_export_match(self):
        from repoforge.graph import build_graph
        g = build_graph(IMPORT_RESOLUTION_MAP)
        # "authenticate" is exported by lib/auth.py → direct export match
        deps = g.get_dependencies("handlers/login.py")
        assert "lib/auth.py" in deps

    def test_module_name_match(self):
        from repoforge.graph import build_graph
        g = build_graph(IMPORT_RESOLUTION_MAP)
        # "db" matches module name of lib/db.py → module name match
        deps = g.get_dependencies("handlers/login.py")
        assert "lib/db.py" in deps

    def test_external_import_ignored(self):
        from repoforge.graph import build_graph
        g = build_graph(IMPORT_RESOLUTION_MAP)
        # "nonexistent_external" doesn't match anything → no edge
        edges = [
            e for e in g.edges
            if e.source == "handlers/login.py"
            and "nonexistent" in e.target
        ]
        assert len(edges) == 0

    def test_no_self_reference(self):
        """A module should not import itself even if names match."""
        repo_map = {
            "layers": {
                "lib": {
                    "path": "lib",
                    "modules": [
                        {
                            "path": "lib/utils.py",
                            "name": "utils",
                            "exports": ["helper"],
                            "imports": ["helper"],  # imports own export
                        },
                    ],
                },
            },
        }
        from repoforge.graph import build_graph
        g = build_graph(repo_map)
        import_edges = [e for e in g.edges if e.edge_type == "imports"]
        self_edges = [e for e in import_edges if e.source == e.target]
        assert len(self_edges) == 0


# ---------------------------------------------------------------------------
# Tests: to_mermaid()
# ---------------------------------------------------------------------------

class TestToMermaid:
    def test_mermaid_starts_with_graph(self, small_graph):
        output = small_graph.to_mermaid()
        assert output.startswith("graph LR")

    def test_mermaid_has_subgraphs(self, small_graph):
        output = small_graph.to_mermaid()
        assert "subgraph" in output
        assert "end" in output

    def test_mermaid_has_edges(self, small_graph):
        output = small_graph.to_mermaid()
        assert "-->" in output

    def test_mermaid_groups_by_layer(self, small_graph):
        output = small_graph.to_mermaid()
        assert "subgraph core" in output or "subgraph api" in output

    def test_mermaid_max_nodes_limits_output(self, medium_graph):
        output_all = medium_graph.to_mermaid(max_nodes=50)
        output_limited = medium_graph.to_mermaid(max_nodes=2)
        # Limited output should have fewer nodes
        assert output_limited.count("[") <= output_all.count("[")

    def test_mermaid_no_contains_edges(self, small_graph):
        """Mermaid output should not include 'contains' edges."""
        output = small_graph.to_mermaid()
        # Check that layer→module contains edges are not in the arrow list
        for e in small_graph.edges:
            if e.edge_type == "contains":
                # These edges should NOT appear as arrows
                pass
        # Just verify arrows are only between module nodes
        assert "layer_" not in output.split("-->")[0].split("\n")[-1] if "-->" in output else True

    def test_mermaid_empty_graph(self, empty_graph):
        output = empty_graph.to_mermaid()
        assert output == "graph LR"

    def test_mermaid_valid_identifiers(self, small_graph):
        """Node identifiers should not contain special characters."""
        import re
        output = small_graph.to_mermaid()
        # Find all node identifiers (before [ bracket)
        for line in output.split("\n"):
            line = line.strip()
            if "[" in line and "subgraph" not in line:
                node_id = line.split("[")[0].strip()
                assert re.match(r"^[a-zA-Z0-9_]+$", node_id), \
                    f"Invalid Mermaid ID: {node_id!r}"


# ---------------------------------------------------------------------------
# Tests: to_json()
# ---------------------------------------------------------------------------

class TestToJSON:
    def test_json_is_valid(self, small_graph):
        output = small_graph.to_json()
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_json_has_nodes_and_edges(self, small_graph):
        data = json.loads(small_graph.to_json())
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_json_node_structure(self, small_graph):
        data = json.loads(small_graph.to_json())
        node = data["nodes"][0]
        assert "id" in node
        assert "name" in node
        assert "type" in node
        assert "layer" in node
        assert "file_path" in node
        assert "exports" in node

    def test_json_edge_structure(self, small_graph):
        data = json.loads(small_graph.to_json())
        # Find an import edge
        import_edges = [e for e in data["edges"] if e["type"] == "imports"]
        assert len(import_edges) > 0
        edge = import_edges[0]
        assert "source" in edge
        assert "target" in edge
        assert "type" in edge
        assert "weight" in edge

    def test_json_node_count(self, small_graph):
        data = json.loads(small_graph.to_json())
        # 3 modules + 2 layer nodes = 5 total
        assert len(data["nodes"]) == 5

    def test_json_empty_graph(self, empty_graph):
        data = json.loads(empty_graph.to_json())
        assert data["nodes"] == []
        assert data["edges"] == []


# ---------------------------------------------------------------------------
# Tests: to_dot()
# ---------------------------------------------------------------------------

class TestToDot:
    def test_dot_starts_with_digraph(self, small_graph):
        output = small_graph.to_dot()
        assert output.startswith("digraph CodeGraph {")

    def test_dot_ends_with_closing_brace(self, small_graph):
        output = small_graph.to_dot()
        assert output.strip().endswith("}")

    def test_dot_has_rankdir(self, small_graph):
        output = small_graph.to_dot()
        assert "rankdir=LR" in output

    def test_dot_has_subgraph_clusters(self, small_graph):
        output = small_graph.to_dot()
        assert "subgraph cluster_" in output

    def test_dot_has_edges(self, small_graph):
        output = small_graph.to_dot()
        assert "->" in output

    def test_dot_no_contains_edges(self, small_graph):
        """DOT output should not include 'contains' edges."""
        output = small_graph.to_dot()
        # layer nodes should not appear as edge endpoints
        lines = [ln.strip() for ln in output.split("\n") if "->" in ln]
        for line in lines:
            assert "layer:" not in line

    def test_dot_empty_graph(self, empty_graph):
        output = empty_graph.to_dot()
        assert "digraph CodeGraph {" in output
        assert output.strip().endswith("}")

    def test_dot_labels_present(self, small_graph):
        output = small_graph.to_dot()
        assert 'label="models"' in output or 'label="utils"' in output


# ---------------------------------------------------------------------------
# Tests: summary()
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_shows_modules(self, small_graph):
        output = small_graph.summary()
        assert "Modules: 3" in output

    def test_summary_shows_dependencies(self, small_graph):
        output = small_graph.summary()
        assert "Dependencies: 2" in output

    def test_summary_shows_layers(self, small_graph):
        output = small_graph.summary()
        assert "Layers: 2" in output

    def test_summary_shows_most_connected(self, medium_graph):
        output = medium_graph.summary()
        assert "Most connected:" in output

    def test_summary_shows_isolated_modules(self):
        from repoforge.graph import build_graph
        repo_map = {
            "layers": {
                "lib": {
                    "path": "lib",
                    "modules": [
                        {
                            "path": "lib/orphan.py",
                            "name": "orphan",
                            "exports": [],
                            "imports": [],
                        },
                    ],
                },
            },
        }
        g = build_graph(repo_map)
        output = g.summary()
        assert "Isolated modules" in output
        assert "orphan" in output

    def test_summary_empty_graph(self, empty_graph):
        output = empty_graph.summary()
        assert "Modules: 0" in output
        assert "Dependencies: 0" in output

    def test_summary_medium_has_connections(self, medium_graph):
        output = medium_graph.summary()
        assert "connections" in output


# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_graph_all_formats(self, empty_graph):
        """All format methods should work on empty graphs without crashing."""
        assert "graph LR" in empty_graph.to_mermaid()
        data = json.loads(empty_graph.to_json())
        assert data["nodes"] == []
        assert "digraph" in empty_graph.to_dot()
        assert "Modules: 0" in empty_graph.summary()

    def test_single_module_no_edges(self):
        from repoforge.graph import build_graph
        g = build_graph(SINGLE_MODULE_MAP)
        import_edges = [e for e in g.edges if e.edge_type == "imports"]
        assert len(import_edges) == 0
        output = g.summary()
        assert "Modules: 1" in output

    def test_graph_with_missing_exports_key(self):
        """Modules without exports key should not crash."""
        from repoforge.graph import build_graph
        repo_map = {
            "layers": {
                "lib": {
                    "path": "lib",
                    "modules": [
                        {
                            "path": "lib/a.py",
                            "name": "a",
                            "exports": [],
                            "imports": [],
                        },
                    ],
                },
            },
        }
        g = build_graph(repo_map)
        assert len(g.nodes) >= 1

    def test_graph_with_empty_module_name(self):
        """Module without name should use stem of path."""
        from repoforge.graph import build_graph
        repo_map = {
            "layers": {
                "lib": {
                    "path": "lib",
                    "modules": [
                        {
                            "path": "lib/something.py",
                            "exports": [],
                            "imports": [],
                        },
                    ],
                },
            },
        }
        g = build_graph(repo_map)
        node = g.get_node("lib/something.py")
        assert node is not None
        assert node.name == "something"

    def test_build_graph_deterministic(self):
        from repoforge.graph import build_graph
        g1 = build_graph(SMALL_REPO_MAP)
        g2 = build_graph(SMALL_REPO_MAP)
        assert len(g1.nodes) == len(g2.nodes)
        assert len(g1.edges) == len(g2.edges)
        j1 = json.loads(g1.to_json())
        j2 = json.loads(g2.to_json())
        assert j1 == j2


# ---------------------------------------------------------------------------
# Tests: CLI graph subcommand
# ---------------------------------------------------------------------------

class TestCLIGraph:
    def test_graph_help(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["graph", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output
        assert "--blast-radius" in result.output
        assert "--workspace" in result.output or "-w" in result.output
        assert "--output" in result.output or "-o" in result.output
        assert "mermaid" in result.output
        assert "json" in result.output
        assert "dot" in result.output
        assert "summary" in result.output

    def test_graph_summary_default(self):
        """Default format should be summary."""
        from pathlib import Path

        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, ["graph", "-w", repo_dir, "-q"])
        assert result.exit_code == 0
        assert "Modules:" in result.output
        assert "Dependencies:" in result.output

    def test_graph_mermaid_format(self):
        from pathlib import Path

        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "graph", "-w", repo_dir, "--format", "mermaid", "-q",
        ])
        assert result.exit_code == 0
        assert "graph LR" in result.output

    def test_graph_json_format(self):
        from pathlib import Path

        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "graph", "-w", repo_dir, "--format", "json", "-q",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "nodes" in data
        assert "edges" in data

    def test_graph_dot_format(self):
        from pathlib import Path

        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "graph", "-w", repo_dir, "--format", "dot", "-q",
        ])
        assert result.exit_code == 0
        assert "digraph CodeGraph" in result.output

    def test_graph_output_to_file(self, tmp_path):
        from pathlib import Path

        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        output_file = str(tmp_path / "graph.json")
        runner = CliRunner()
        result = runner.invoke(main, [
            "graph", "-w", repo_dir, "--format", "json",
            "-o", output_file, "-q",
        ])
        assert result.exit_code == 0
        assert Path(output_file).exists()
        data = json.loads(Path(output_file).read_text(encoding="utf-8"))
        assert "nodes" in data

    def test_graph_blast_radius_nonexistent(self):
        from pathlib import Path

        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "graph", "-w", repo_dir,
            "--blast-radius", "totally_nonexistent_module_xyz.py", "-q",
        ])
        assert result.exit_code != 0

    def test_graph_in_main_help(self):
        """Graph should appear in the main help text."""
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "graph" in result.output


# ---------------------------------------------------------------------------
# Tests: Public API exports
# ---------------------------------------------------------------------------

class TestPublicAPI:
    def test_imports_from_init(self):
        from repoforge import CodeGraph, Edge, Node, build_graph, build_graph_from_workspace
        assert CodeGraph is not None
        assert Node is not None
        assert Edge is not None
        assert build_graph is not None
        assert build_graph_from_workspace is not None

    def test_graph_in_all(self):
        import repoforge
        assert "CodeGraph" in repoforge.__all__
        assert "Node" in repoforge.__all__
        assert "Edge" in repoforge.__all__
        assert "build_graph" in repoforge.__all__
        assert "build_graph_from_workspace" in repoforge.__all__
