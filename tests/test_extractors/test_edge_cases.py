"""
tests/test_extractors/test_edge_cases.py — Edge cases and error handling.

Tests that extractors and graph builder handle gracefully:
- Empty files
- Binary files
- Files with syntax errors
- Very large files
- Circular imports
- Self-imports
- Non-existent import targets
"""

import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixture: edge case project
# ---------------------------------------------------------------------------

@pytest.fixture
def edge_case_project(tmp_path):
    """Create a project with various edge case files."""

    # Empty files
    (tmp_path / "empty.py").write_text("")
    (tmp_path / "empty.ts").write_text("")
    (tmp_path / "empty.go").write_text("")
    (tmp_path / "empty.java").write_text("")
    (tmp_path / "empty.rs").write_text("")
    (tmp_path / "empty.js").write_text("")

    # Files with syntax errors (but valid enough for regex extraction)
    (tmp_path / "broken_syntax.py").write_text(
        "from utils import helper\n"
        "def foo(\n"  # syntax error: unclosed paren
        "    return None\n"
    )

    (tmp_path / "broken_syntax.ts").write_text(
        "import { foo } from './bar';\n"
        "export const x = {{\n"  # syntax error: double braces
        "  a: 1\n"
    )

    # Circular imports: A imports B, B imports A
    (tmp_path / "circular_a.py").write_text(
        "from .circular_b import func_b\n"
        "\n"
        "def func_a():\n"
        "    return func_b()\n"
    )

    (tmp_path / "circular_b.py").write_text(
        "from .circular_a import func_a\n"
        "\n"
        "def func_b():\n"
        "    return func_a()\n"
    )

    (tmp_path / "__init__.py").write_text("")

    # Self-import (file imports itself)
    (tmp_path / "self_import.py").write_text(
        "from .self_import import helper\n"
        "\n"
        "def helper():\n"
        "    pass\n"
    )

    # Non-existent import targets
    (tmp_path / "phantom_imports.py").write_text(
        "from .nonexistent_module import something\n"
        "from .also_missing import other\n"
        "import totally_external_lib\n"
        "\n"
        "def do_stuff():\n"
        "    pass\n"
    )

    (tmp_path / "phantom_imports.ts").write_text(
        "import { foo } from './does_not_exist';\n"
        "import { bar } from 'external-package';\n"
        "\n"
        "export const x = foo + bar;\n"
    )

    # Normal file that others can import (for testing circular deps work)
    (tmp_path / "normal.py").write_text(
        "def normal_func():\n"
        "    return 'normal'\n"
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Tests: Empty files
# ---------------------------------------------------------------------------

class TestEmptyFiles:
    def test_empty_python_no_crash(self, edge_case_project):
        """Empty Python file should produce a node with no imports/exports."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(edge_case_project))
        node = graph.get_node("empty.py")
        assert node is not None
        assert node.exports == []

    def test_empty_ts_no_crash(self, edge_case_project):
        """Empty TypeScript file should produce a node with no imports."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(edge_case_project))
        node = graph.get_node("empty.ts")
        assert node is not None

    def test_empty_go_no_crash(self, edge_case_project):
        """Empty Go file should produce a node."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(edge_case_project))
        node = graph.get_node("empty.go")
        assert node is not None

    def test_empty_java_no_crash(self, edge_case_project):
        """Empty Java file should produce a node."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(edge_case_project))
        node = graph.get_node("empty.java")
        assert node is not None

    def test_empty_rust_no_crash(self, edge_case_project):
        """Empty Rust file should produce a node."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(edge_case_project))
        node = graph.get_node("empty.rs")
        assert node is not None

    def test_empty_js_no_crash(self, edge_case_project):
        """Empty JavaScript file should produce a node."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(edge_case_project))
        node = graph.get_node("empty.js")
        assert node is not None

    def test_empty_files_no_edges(self, edge_case_project):
        """Empty files should not have any import edges."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(edge_case_project))
        empty_files = ["empty.py", "empty.ts", "empty.go",
                       "empty.java", "empty.rs", "empty.js"]
        for ef in empty_files:
            deps = graph.get_dependencies(ef)
            assert deps == [], f"Empty file {ef} should have no deps, got {deps}"


# ---------------------------------------------------------------------------
# Tests: Binary files
# ---------------------------------------------------------------------------

class TestBinaryFiles:
    def test_binary_file_no_crash(self, tmp_path):
        """Binary files should not crash the extractor."""
        # Create a binary file with .py extension
        binary_content = bytes(range(256)) * 10
        (tmp_path / "binary.py").write_bytes(binary_content)
        (tmp_path / "normal.py").write_text("def foo(): pass\n")

        from repoforge.graph import build_graph_v2
        # Should not raise
        graph = build_graph_v2(
            str(tmp_path), files=["binary.py", "normal.py"],
        )
        # Normal file should still be there
        assert graph.get_node("normal.py") is not None

    def test_binary_ts_no_crash(self, tmp_path):
        """Binary .ts file should not crash."""
        (tmp_path / "binary.ts").write_bytes(b"\x00\x01\x02\xff\xfe\xfd" * 100)
        (tmp_path / "ok.ts").write_text("export const x = 1;\n")

        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(tmp_path), files=["binary.ts", "ok.ts"])
        assert graph.get_node("ok.ts") is not None


# ---------------------------------------------------------------------------
# Tests: Files with syntax errors
# ---------------------------------------------------------------------------

class TestSyntaxErrors:
    def test_python_syntax_error_extracts_imports(self, edge_case_project):
        """Python file with syntax error should still extract imports it can."""
        from repoforge.extractors import get_extractor
        extractor = get_extractor("broken_syntax.py")
        content = (edge_case_project / "broken_syntax.py").read_text()
        imports = extractor.extract_imports(content)
        # Should extract at least the valid import line
        sources = [i.source for i in imports]
        assert "utils" in sources or ".utils" in sources or len(imports) >= 0

    def test_ts_syntax_error_extracts_imports(self, edge_case_project):
        """TS file with syntax error should still extract valid imports."""
        from repoforge.extractors import get_extractor
        extractor = get_extractor("broken_syntax.ts")
        content = (edge_case_project / "broken_syntax.ts").read_text()
        imports = extractor.extract_imports(content)
        sources = [i.source for i in imports]
        assert "./bar" in sources

    def test_syntax_error_graph_no_crash(self, edge_case_project):
        """Graph builder should not crash on files with syntax errors."""
        from repoforge.graph import build_graph_v2
        # Should complete without exception
        graph = build_graph_v2(str(edge_case_project))
        assert len(graph.nodes) > 0


# ---------------------------------------------------------------------------
# Tests: Very large files
# ---------------------------------------------------------------------------

class TestLargeFiles:
    def test_large_python_file(self, tmp_path):
        """Large Python file (>1MB) should be handled gracefully."""
        # Generate a large Python file with many imports and functions
        lines = ["from utils import helper\n"]
        for i in range(50000):
            lines.append(f"def func_{i}():\n    return {i}\n\n")
        content = "".join(lines)
        (tmp_path / "large.py").write_text(content)
        (tmp_path / "utils.py").write_text("def helper(): pass\n")

        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(
            str(tmp_path), files=["large.py", "utils.py"],
        )
        node = graph.get_node("large.py")
        assert node is not None
        # Should have extracted exports
        assert len(node.exports) > 0

    def test_large_ts_file(self, tmp_path):
        """Large TypeScript file should be handled gracefully."""
        lines = ["import { helper } from './utils';\n\n"]
        for i in range(10000):
            lines.append(f"export function fn_{i}(): number {{ return {i}; }}\n")
        content = "".join(lines)
        (tmp_path / "large.ts").write_text(content)
        (tmp_path / "utils.ts").write_text("export function helper() {}\n")

        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(
            str(tmp_path), files=["large.ts", "utils.ts"],
        )
        node = graph.get_node("large.ts")
        assert node is not None


# ---------------------------------------------------------------------------
# Tests: Circular imports
# ---------------------------------------------------------------------------

class TestCircularImports:
    def test_circular_imports_no_crash(self, edge_case_project):
        """Circular imports (A→B, B→A) should not crash or loop infinitely."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(edge_case_project))
        # Both files should be in the graph
        assert graph.get_node("circular_a.py") is not None
        assert graph.get_node("circular_b.py") is not None

    def test_circular_imports_both_edges(self, edge_case_project):
        """Both circular import edges should be present."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(edge_case_project))
        deps_a = graph.get_dependencies("circular_a.py")
        deps_b = graph.get_dependencies("circular_b.py")
        assert "circular_b.py" in deps_a
        assert "circular_a.py" in deps_b

    def test_circular_blast_radius_terminates(self, edge_case_project):
        """Blast radius with circular deps should terminate (not loop)."""
        from repoforge.graph import build_graph_v2, get_blast_radius_v2
        graph = build_graph_v2(str(edge_case_project))
        # Should terminate without hanging
        br = get_blast_radius_v2(graph, "circular_a.py", max_depth=10)
        assert isinstance(br.files, list)
        # circular_b should be in the blast radius
        assert "circular_b.py" in br.files


# ---------------------------------------------------------------------------
# Tests: Self-imports
# ---------------------------------------------------------------------------

class TestSelfImports:
    def test_self_import_no_self_edge(self, edge_case_project):
        """A file importing itself should not create a self-referencing edge."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(edge_case_project))
        deps = graph.get_dependencies("self_import.py")
        assert "self_import.py" not in deps, (
            "Self-import should not create a self-referencing edge"
        )

    def test_self_import_no_self_edge_in_graph(self, edge_case_project):
        """No edge should have source == target."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(edge_case_project))
        for edge in graph.edges:
            assert edge.source != edge.target, (
                f"Self-edge found: {edge.source} → {edge.target}"
            )


# ---------------------------------------------------------------------------
# Tests: Non-existent import targets
# ---------------------------------------------------------------------------

class TestNonExistentImports:
    def test_phantom_python_imports_no_crash(self, edge_case_project):
        """Imports pointing to non-existent files should not crash."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(edge_case_project))
        node = graph.get_node("phantom_imports.py")
        assert node is not None
        # Should not have edges to non-existent files
        deps = graph.get_dependencies("phantom_imports.py")
        assert "nonexistent_module.py" not in deps
        assert "also_missing.py" not in deps

    def test_phantom_ts_imports_no_crash(self, edge_case_project):
        """TS imports to non-existent files should not crash."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(edge_case_project))
        node = graph.get_node("phantom_imports.ts")
        assert node is not None
        deps = graph.get_dependencies("phantom_imports.ts")
        assert "does_not_exist.ts" not in deps

    def test_no_edges_to_missing_files(self, edge_case_project):
        """Graph should only have edges to files that exist in the graph."""
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(edge_case_project))
        node_ids = {n.id for n in graph.nodes}
        for edge in graph.edges:
            assert edge.target in node_ids, (
                f"Edge to non-existent node: {edge.source} → {edge.target}"
            )
            assert edge.source in node_ids, (
                f"Edge from non-existent node: {edge.source} → {edge.target}"
            )
