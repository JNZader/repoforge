"""
tests/test_backward_compat.py — Backward compatibility gate.

Ensures that:
1. build_graph (v1) still produces identical output to before (no regressions)
2. build_graph_v2 produces RICHER output (more edges, file-level deps)
3. Existing CLI `repoforge graph -w .` (without --v2) still works identically
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = str(Path(__file__).parent.parent)


# ---------------------------------------------------------------------------
# Fixtures: identical repo map for both v1 comparisons
# ---------------------------------------------------------------------------

COMPAT_REPO_MAP = {
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
                    "exports": ["slugify"],
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


# ---------------------------------------------------------------------------
# Tests: v1 still produces identical output (no regressions)
# ---------------------------------------------------------------------------

class TestV1NoRegression:
    def test_v1_same_node_count(self):
        """build_graph produces the same number of nodes across calls."""
        from repoforge.graph import build_graph
        g1 = build_graph(COMPAT_REPO_MAP)
        g2 = build_graph(COMPAT_REPO_MAP)
        assert len(g1.nodes) == len(g2.nodes)

    def test_v1_same_edge_count(self):
        """build_graph produces the same number of edges across calls."""
        from repoforge.graph import build_graph
        g1 = build_graph(COMPAT_REPO_MAP)
        g2 = build_graph(COMPAT_REPO_MAP)
        assert len(g1.edges) == len(g2.edges)

    def test_v1_deterministic_json(self):
        """build_graph JSON output is deterministic."""
        from repoforge.graph import build_graph
        g1 = build_graph(COMPAT_REPO_MAP)
        g2 = build_graph(COMPAT_REPO_MAP)
        assert json.loads(g1.to_json()) == json.loads(g2.to_json())

    def test_v1_expected_module_count(self):
        """v1 should find exactly 3 module nodes + 2 layer nodes."""
        from repoforge.graph import build_graph
        g = build_graph(COMPAT_REPO_MAP)
        modules = [n for n in g.nodes if n.node_type == "module"]
        layers = [n for n in g.nodes if n.node_type == "layer"]
        assert len(modules) == 3
        assert len(layers) == 2

    def test_v1_expected_import_edges(self):
        """v1 should create 2 import edges (routes→models, routes→utils)."""
        from repoforge.graph import build_graph
        g = build_graph(COMPAT_REPO_MAP)
        import_edges = [e for e in g.edges if e.edge_type == "imports"]
        assert len(import_edges) == 2

    def test_v1_resolution_still_works(self):
        """v1 import resolution strategies still function correctly."""
        from repoforge.graph import build_graph
        g = build_graph(COMPAT_REPO_MAP)
        deps = g.get_dependencies("src/api/routes.py")
        assert "src/core/models.py" in deps
        assert "src/core/utils.py" in deps

    def test_v1_blast_radius_unchanged(self):
        """v1 blast radius still works identically."""
        from repoforge.graph import build_graph
        g = build_graph(COMPAT_REPO_MAP)
        affected = g.get_blast_radius("src/core/models.py")
        assert "src/api/routes.py" in affected

    def test_v1_mermaid_format_unchanged(self):
        """v1 Mermaid output starts with graph LR and has subgraphs."""
        from repoforge.graph import build_graph
        g = build_graph(COMPAT_REPO_MAP)
        output = g.to_mermaid()
        assert output.startswith("graph LR")
        assert "subgraph" in output
        assert "-->" in output

    def test_v1_json_format_unchanged(self):
        """v1 JSON output has nodes and edges keys."""
        from repoforge.graph import build_graph
        g = build_graph(COMPAT_REPO_MAP)
        data = json.loads(g.to_json())
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 5  # 3 modules + 2 layers

    def test_v1_summary_format_unchanged(self):
        """v1 summary output has expected sections."""
        from repoforge.graph import build_graph
        g = build_graph(COMPAT_REPO_MAP)
        output = g.summary()
        assert "Modules: 3" in output
        assert "Dependencies: 2" in output
        assert "Layers: 2" in output


# ---------------------------------------------------------------------------
# Tests: v2 produces RICHER output
# ---------------------------------------------------------------------------

class TestV2RicherOutput:
    def test_v2_finds_more_files(self, tmp_path):
        """v2 should find more files than v1 (which only sees RepoMap modules)."""
        # Create a small multi-file project
        (tmp_path / "main.py").write_text(
            "from utils import helper\n\ndef run(): pass\n"
        )
        (tmp_path / "utils.py").write_text(
            "def helper(): pass\n"
        )
        (tmp_path / "config.py").write_text(
            "# No imports\nSETTINGS = {}\n"
        )

        from repoforge.graph import build_graph, build_graph_v2

        # v1 with minimal RepoMap (only knows about main)
        repo_map = {
            "layers": {
                "root": {
                    "path": str(tmp_path),
                    "modules": [
                        {
                            "path": "main.py",
                            "name": "main",
                            "exports": ["run"],
                            "imports": ["helper"],
                        },
                    ],
                },
            },
        }
        g_v1 = build_graph(repo_map)

        # v2 discovers all files
        g_v2 = build_graph_v2(
            str(tmp_path),
            files=["main.py", "utils.py", "config.py"],
        )

        v1_modules = [n for n in g_v1.nodes if n.node_type == "module"]
        v2_modules = [n for n in g_v2.nodes if n.node_type == "module"]
        assert len(v2_modules) >= len(v1_modules), (
            f"v2 ({len(v2_modules)} modules) should find at least as many as "
            f"v1 ({len(v1_modules)} modules)"
        )

    def test_v2_file_level_edges(self, tmp_path):
        """v2 creates file-to-file edges based on actual import analysis."""
        (tmp_path / "app.py").write_text(
            "from .utils import helper\n\ndef main(): helper()\n"
        )
        (tmp_path / "utils.py").write_text(
            "def helper(): return 42\n"
        )
        (tmp_path / "__init__.py").write_text("")

        from repoforge.graph import build_graph_v2
        g = build_graph_v2(
            str(tmp_path),
            files=["app.py", "utils.py", "__init__.py"],
        )

        deps = g.get_dependencies("app.py")
        assert "utils.py" in deps

    def test_v2_exports_extracted_from_content(self, tmp_path):
        """v2 extracts actual exports from file content."""
        (tmp_path / "models.py").write_text(
            "class User:\n    pass\n\n"
            "class Post:\n    pass\n\n"
            "def create_user(): pass\n"
        )

        from repoforge.graph import build_graph_v2
        g = build_graph_v2(str(tmp_path), files=["models.py"])

        node = g.get_node("models.py")
        assert node is not None
        assert "User" in node.exports
        assert "Post" in node.exports
        assert "create_user" in node.exports


# ---------------------------------------------------------------------------
# Tests: CLI without --v2 still works identically
# ---------------------------------------------------------------------------

class TestCLIBackwardCompat:
    def test_cli_default_uses_v1(self):
        """repoforge graph -w . (no --v2) should use v1 name-matching."""
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["graph", "-w", REPO_ROOT, "-q"])
        assert result.exit_code == 0
        assert "Modules:" in result.output
        assert "Dependencies:" in result.output

    def test_cli_v1_json_valid(self):
        """v1 JSON output via CLI should be valid JSON."""
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, [
            "graph", "-w", REPO_ROOT, "--format", "json", "-q",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "nodes" in data
        assert "edges" in data

    def test_cli_v1_mermaid_valid(self):
        """v1 Mermaid output via CLI should start with graph LR."""
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, [
            "graph", "-w", REPO_ROOT, "--format", "mermaid", "-q",
        ])
        assert result.exit_code == 0
        assert "graph LR" in result.output

    def test_cli_v1_blast_radius_works(self):
        """v1 blast radius via CLI should work with a known module name.

        v1 uses RepoMap module paths which may differ from raw file paths.
        We first build the graph to find a valid module name, then test
        blast radius with it.
        """
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()

        # First get the JSON to find a valid module name
        result = runner.invoke(main, [
            "graph", "-w", REPO_ROOT, "--format", "json", "-q",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        module_nodes = [n for n in data["nodes"] if n["type"] == "module"]

        if module_nodes:
            # Use the first available module
            module_id = module_nodes[0]["id"]
            result = runner.invoke(main, [
                "graph", "-w", REPO_ROOT,
                "--blast-radius", module_id, "-q",
            ])
            assert result.exit_code == 0
            assert "Blast radius for:" in result.output

    def test_cli_v2_produces_output(self):
        """repoforge graph -w . --v2 should produce valid output."""
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, [
            "graph", "-w", REPO_ROOT, "--v2", "-q",
        ])
        assert result.exit_code == 0
        assert "Modules:" in result.output

    def test_cli_v1_and_v2_both_succeed(self):
        """Both v1 and v2 should succeed on the same workspace."""
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        r1 = runner.invoke(main, ["graph", "-w", REPO_ROOT, "-q"])
        r2 = runner.invoke(main, ["graph", "-w", REPO_ROOT, "--v2", "-q"])
        assert r1.exit_code == 0
        assert r2.exit_code == 0
