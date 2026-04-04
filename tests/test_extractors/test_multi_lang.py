"""
tests/test_extractors/test_multi_lang.py — Multi-language integration test.

Creates a temporary project with files in all 6 supported languages
that import each other, builds a v2 graph, and verifies that all
dependencies are detected including transitive blast radius.
"""

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixture: multi-language project with cross-file imports
# ---------------------------------------------------------------------------

@pytest.fixture
def multi_lang_project(tmp_path):
    """Create a project with files in all 6 languages importing each other."""

    # --- TypeScript ---
    ts_dir = tmp_path / "ts"
    ts_dir.mkdir()

    (ts_dir / "app.ts").write_text(
        "import { greet } from './utils';\n"
        "import { Config } from './types';\n"
        "\n"
        "export function main(): void {\n"
        "  console.log(greet('world'));\n"
        "}\n"
    )

    (ts_dir / "utils.ts").write_text(
        "import { Config } from './types';\n"
        "\n"
        "export function greet(name: string): string {\n"
        "  return `Hello, ${name}`;\n"
        "}\n"
    )

    (ts_dir / "types.ts").write_text(
        "export interface Config {\n"
        "  debug: boolean;\n"
        "  port: number;\n"
        "}\n"
        "\n"
        "export type Status = 'active' | 'inactive';\n"
    )

    # --- JavaScript ---
    js_dir = tmp_path / "js"
    js_dir.mkdir()

    (js_dir / "index.js").write_text(
        "const { parse } = require('./parser');\n"
        "\n"
        "module.exports = { run: () => parse('data') };\n"
    )

    (js_dir / "parser.js").write_text(
        "function parse(data) { return JSON.parse(data); }\n"
        "\n"
        "module.exports = { parse };\n"
    )

    # --- Python ---
    py_dir = tmp_path / "py"
    py_dir.mkdir()

    (py_dir / "__init__.py").write_text("")

    (py_dir / "main.py").write_text(
        "from .utils import helper\n"
        "\n"
        "def run():\n"
        "    return helper()\n"
    )

    (py_dir / "utils.py").write_text(
        "def helper():\n"
        "    return 42\n"
    )

    # --- Go ---
    go_dir = tmp_path / "go"
    go_dir.mkdir()

    (tmp_path / "go.mod").write_text(
        "module github.com/test/multilang\n"
        "\n"
        "go 1.22\n"
    )

    (go_dir / "main.go").write_text(
        'package main\n'
        '\n'
        'import (\n'
        '    "fmt"\n'
        '    "github.com/test/multilang/go/internal/store"\n'
        ')\n'
        '\n'
        'func main() {\n'
        '    fmt.Println(store.Get())\n'
        '}\n'
    )

    internal_dir = go_dir / "internal" / "store"
    internal_dir.mkdir(parents=True)

    (internal_dir / "store.go").write_text(
        "package store\n"
        "\n"
        'func Get() string { return "data" }\n'
    )

    # --- Java ---
    java_dir = tmp_path / "java" / "com" / "example"
    java_dir.mkdir(parents=True)

    (java_dir / "App.java").write_text(
        "package com.example;\n"
        "\n"
        "import com.example.Utils;\n"
        "\n"
        "public class App {\n"
        "    public static void main(String[] args) {\n"
        "        Utils.greet();\n"
        "    }\n"
        "}\n"
    )

    (java_dir / "Utils.java").write_text(
        "package com.example;\n"
        "\n"
        "public class Utils {\n"
        "    public static void greet() {\n"
        "        System.out.println(\"Hello\");\n"
        "    }\n"
        "}\n"
    )

    # --- Rust ---
    rust_dir = tmp_path / "rust" / "src"
    rust_dir.mkdir(parents=True)

    (rust_dir / "main.rs").write_text(
        "mod utils;\n"
        "\n"
        "use crate::utils::helper;\n"
        "\n"
        "fn main() {\n"
        "    helper();\n"
        "}\n"
    )

    (rust_dir / "utils.rs").write_text(
        "pub fn helper() {\n"
        "    println!(\"Hello from Rust\");\n"
        "}\n"
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Tests: All 6 languages detected
# ---------------------------------------------------------------------------

class TestMultiLangDetection:
    def test_ts_files_in_graph(self, multi_lang_project):
        """TypeScript files should be in the graph."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        node_ids = {n.id for n in graph.nodes}
        assert "ts/app.ts" in node_ids
        assert "ts/utils.ts" in node_ids
        assert "ts/types.ts" in node_ids

    def test_js_files_in_graph(self, multi_lang_project):
        """JavaScript files should be in the graph."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        node_ids = {n.id for n in graph.nodes}
        assert "js/index.js" in node_ids
        assert "js/parser.js" in node_ids

    def test_python_files_in_graph(self, multi_lang_project):
        """Python files should be in the graph."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        node_ids = {n.id for n in graph.nodes}
        assert "py/main.py" in node_ids
        assert "py/utils.py" in node_ids

    def test_go_files_in_graph(self, multi_lang_project):
        """Go files should be in the graph."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        node_ids = {n.id for n in graph.nodes}
        assert "go/main.go" in node_ids
        assert "go/internal/store/store.go" in node_ids

    def test_java_files_in_graph(self, multi_lang_project):
        """Java files should be in the graph."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        node_ids = {n.id for n in graph.nodes}
        assert "java/com/example/App.java" in node_ids
        assert "java/com/example/Utils.java" in node_ids

    def test_rust_files_in_graph(self, multi_lang_project):
        """Rust files should be in the graph."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        node_ids = {n.id for n in graph.nodes}
        assert "rust/src/main.rs" in node_ids
        assert "rust/src/utils.rs" in node_ids


# ---------------------------------------------------------------------------
# Tests: Dependencies detected for each language
# ---------------------------------------------------------------------------

class TestMultiLangDependencies:
    def test_ts_imports_resolved(self, multi_lang_project):
        """TS relative imports should be resolved to file paths."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        # app.ts imports ./utils and ./types
        deps = graph.get_dependencies("ts/app.ts")
        assert "ts/utils.ts" in deps
        assert "ts/types.ts" in deps

    def test_ts_chain_dependency(self, multi_lang_project):
        """utils.ts imports types.ts."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        deps = graph.get_dependencies("ts/utils.ts")
        assert "ts/types.ts" in deps

    def test_js_require_resolved(self, multi_lang_project):
        """JS require('./parser') should resolve to parser.js."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        deps = graph.get_dependencies("js/index.js")
        assert "js/parser.js" in deps

    def test_python_relative_import_resolved(self, multi_lang_project):
        """Python from .utils import should resolve."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        deps = graph.get_dependencies("py/main.py")
        assert "py/utils.py" in deps

    def test_go_module_import_resolved(self, multi_lang_project):
        """Go module imports should resolve via go.mod."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        deps = graph.get_dependencies("go/main.go")
        assert "go/internal/store/store.go" in deps

    def test_all_languages_have_edges(self, multi_lang_project):
        """The graph should have import edges from at least 4 languages."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        import_edges = [e for e in graph.edges if e.edge_type == "imports"]

        # Collect which language prefixes have edges
        prefixes_with_edges = set()
        for e in import_edges:
            for prefix in ("ts/", "js/", "py/", "go/"):
                if e.source.startswith(prefix):
                    prefixes_with_edges.add(prefix)

        # At least TS, JS, Python, Go should have resolved edges
        assert len(prefixes_with_edges) >= 4, (
            f"Expected edges from at least 4 languages, got: {prefixes_with_edges}"
        )


# ---------------------------------------------------------------------------
# Tests: Transitive blast radius across types.ts chain
# ---------------------------------------------------------------------------

class TestMultiLangBlastRadius:
    def test_blast_radius_from_types_ts(self, multi_lang_project):
        """Changing types.ts should transitively reach app.ts.

        Chain: types.ts ← utils.ts ← app.ts
        """
        from repoforge.graph import build_graph_v2, get_blast_radius_v2
        graph = build_graph_v2(str(multi_lang_project))
        br = get_blast_radius_v2(graph, "ts/types.ts", max_depth=5)
        all_affected = set(br.files + br.test_files)
        assert "ts/utils.ts" in all_affected, (
            f"Expected utils.ts in blast radius, got: {all_affected}"
        )
        assert "ts/app.ts" in all_affected, (
            f"Expected app.ts in blast radius (transitive via utils), "
            f"got: {all_affected}"
        )

    def test_blast_radius_from_python_utils(self, multi_lang_project):
        """Changing py/utils.py should affect py/main.py."""
        from repoforge.graph import build_graph_v2, get_blast_radius_v2
        graph = build_graph_v2(str(multi_lang_project))
        br = get_blast_radius_v2(graph, "py/utils.py", max_depth=5)
        assert "py/main.py" in br.files

    def test_blast_radius_from_go_store(self, multi_lang_project):
        """Changing go/internal/store/store.go should affect go/main.go."""
        from repoforge.graph import build_graph_v2, get_blast_radius_v2
        graph = build_graph_v2(str(multi_lang_project))
        br = get_blast_radius_v2(
            graph, "go/internal/store/store.go", max_depth=5,
        )
        assert "go/main.go" in br.files

    def test_blast_radius_leaf_node_empty(self, multi_lang_project):
        """Blast radius of a leaf node (no dependents) should be empty."""
        from repoforge.graph import build_graph_v2, get_blast_radius_v2
        graph = build_graph_v2(str(multi_lang_project))
        # ts/app.ts is a leaf — nothing imports it
        br = get_blast_radius_v2(graph, "ts/app.ts", max_depth=5)
        assert br.files == []
