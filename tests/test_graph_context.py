"""
tests/test_graph_context.py — Tests for graph context builder.

Tests cover:
- build_graph_context returns non-empty string for a real project
- format_graph_context produces expected markdown sections
- build_short_graph_context is shorter than full context
- build_module_graph_context includes blast radius info
- Graceful fallback: empty string for empty graphs
- Graceful fallback: build_graph_context returns empty on invalid path
- Integration: docs generator includes graph context in prompts
- Integration: skills generator includes blast radius per module
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from repoforge.graph import CodeGraph, Node, Edge, build_graph_v2
from repoforge.graph_context import (
    build_graph_context,
    build_graph_context_from_graph,
    format_graph_context,
    build_short_graph_context,
    build_module_graph_context,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_graph():
    """Build a small graph with known topology for testing."""
    g = CodeGraph()
    # Modules: A imports B, B imports C, D is isolated
    g.add_node(Node(id="src/a.py", name="a", node_type="module", file_path="src/a.py", exports=["func_a"]))
    g.add_node(Node(id="src/b.py", name="b", node_type="module", file_path="src/b.py", exports=["func_b"]))
    g.add_node(Node(id="src/c.py", name="c", node_type="module", file_path="src/c.py", exports=["func_c"]))
    g.add_node(Node(id="src/d.py", name="d", node_type="module", file_path="src/d.py", exports=["func_d"]))

    g.add_edge(Edge(source="src/a.py", target="src/b.py", edge_type="imports"))
    g.add_edge(Edge(source="src/b.py", target="src/c.py", edge_type="imports"))

    return g


@pytest.fixture
def empty_graph():
    return CodeGraph()


@pytest.fixture
def minimal_repo_map():
    return {
        "root": "/fake/project",
        "tech_stack": ["Python"],
        "entry_points": ["main.py"],
        "config_files": ["pyproject.toml"],
        "layers": {
            "main": {
                "path": ".",
                "modules": [
                    {
                        "path": "scanner.py",
                        "name": "scanner",
                        "language": "Python",
                        "exports": ["scan_repo"],
                        "imports": [],
                        "summary_hint": "Scans repos",
                    },
                ],
            }
        },
        "repoforge_config": {},
        "stats": {"total_files": 5, "rg_available": True, "rg_version": "14.0"},
    }


# ---------------------------------------------------------------------------
# format_graph_context
# ---------------------------------------------------------------------------

class TestFormatGraphContext:
    def test_returns_nonempty_for_graph_with_edges(self, sample_graph):
        result = format_graph_context(sample_graph)
        assert result != ""
        assert "Dependency Analysis" in result

    def test_includes_module_count(self, sample_graph):
        result = format_graph_context(sample_graph)
        assert "**Modules**: 4" in result

    def test_includes_dependency_count(self, sample_graph):
        result = format_graph_context(sample_graph)
        assert "**Dependencies**: 2" in result

    def test_includes_isolated_count(self, sample_graph):
        result = format_graph_context(sample_graph)
        assert "**Isolated**: 1" in result

    def test_includes_most_connected(self, sample_graph):
        result = format_graph_context(sample_graph)
        assert "Most Connected" in result
        # b.py has 2 connections (imported by a, imports c)
        assert "b.py" in result

    def test_includes_mermaid_diagram(self, sample_graph):
        result = format_graph_context(sample_graph)
        assert "```mermaid" in result
        assert "graph LR" in result

    def test_returns_empty_for_empty_graph(self, empty_graph):
        result = format_graph_context(empty_graph)
        assert result == ""

    def test_returns_empty_for_graph_with_no_modules(self):
        g = CodeGraph()
        g.add_node(Node(id="layer:core", name="core", node_type="layer"))
        result = format_graph_context(g)
        assert result == ""


# ---------------------------------------------------------------------------
# build_short_graph_context
# ---------------------------------------------------------------------------

class TestShortGraphContext:
    def test_shorter_than_full(self, sample_graph):
        full = format_graph_context(sample_graph)
        short = build_short_graph_context(sample_graph)
        assert len(short) < len(full)

    def test_includes_dependency_summary(self, sample_graph):
        short = build_short_graph_context(sample_graph)
        assert "Dependency Summary" in short
        assert "**Modules**: 4" in short

    def test_returns_empty_for_empty_graph(self, empty_graph):
        assert build_short_graph_context(empty_graph) == ""


# ---------------------------------------------------------------------------
# build_module_graph_context
# ---------------------------------------------------------------------------

class TestModuleGraphContext:
    def test_includes_dependencies(self, sample_graph):
        result = build_module_graph_context(sample_graph, "src/a.py")
        assert "Module Dependencies" in result
        assert "b.py" in result

    def test_includes_dependents(self, sample_graph):
        result = build_module_graph_context(sample_graph, "src/b.py")
        assert "Imported by" in result
        assert "a.py" in result

    def test_includes_blast_radius(self, sample_graph):
        # Changing c.py affects b.py (which imports c), and transitively a.py
        result = build_module_graph_context(sample_graph, "src/c.py")
        assert "Blast radius" in result

    def test_returns_empty_for_unknown_module(self, sample_graph):
        result = build_module_graph_context(sample_graph, "nonexistent.py")
        assert result == ""

    def test_isolated_module_shows_no_impact(self, sample_graph):
        result = build_module_graph_context(sample_graph, "src/d.py")
        assert "isolated" in result.lower() or "none" in result.lower()


# ---------------------------------------------------------------------------
# build_graph_context (with real project)
# ---------------------------------------------------------------------------

class TestBuildGraphContext:
    def test_returns_nonempty_for_repoforge(self):
        """Graph context on the repoforge project itself should produce output."""
        root = str(Path(__file__).parent.parent)
        result = build_graph_context(root)
        assert result != ""
        assert "Dependency Analysis" in result

    def test_returns_empty_for_invalid_path(self):
        result = build_graph_context("/nonexistent/path/that/does/not/exist")
        assert result == ""

    def test_build_graph_context_from_graph_matches_format(self, sample_graph):
        result = build_graph_context_from_graph(sample_graph)
        assert result == format_graph_context(sample_graph)


# ---------------------------------------------------------------------------
# Graceful fallback: generators still work when graph fails
# ---------------------------------------------------------------------------

class TestGracefulFallback:
    def test_docs_generator_works_without_graph(self, minimal_repo_map):
        """Docs generator should not crash if graph building raises."""
        from repoforge.docs_prompts import get_chapter_prompts

        # Call with empty graph context — should work fine
        chapters = get_chapter_prompts(
            minimal_repo_map, "English", "TestProject",
            graph_context="",
            short_graph_context="",
        )
        assert len(chapters) > 0
        # Prompts should still be valid without graph context
        for ch in chapters:
            assert ch["system"]
            assert ch["user"]

    def test_skill_prompt_works_without_graph(self, minimal_repo_map):
        """skill_prompt should work fine with empty graph_context."""
        from repoforge.prompts import skill_prompt

        module = minimal_repo_map["layers"]["main"]["modules"][0]
        system, user = skill_prompt(
            module, "main", minimal_repo_map,
            graph_context="",
        )
        assert system
        assert user
        assert "scanner" in user

    def test_layer_skill_prompt_works_without_graph(self, minimal_repo_map):
        """layer_skill_prompt should work fine with empty graph_context."""
        from repoforge.prompts import layer_skill_prompt

        layer = minimal_repo_map["layers"]["main"]
        system, user = layer_skill_prompt(
            "main", layer, minimal_repo_map,
            graph_context="",
        )
        assert system
        assert user


# ---------------------------------------------------------------------------
# Integration: graph context appears in generated prompts
# ---------------------------------------------------------------------------

class TestPromptIntegration:
    def test_skill_prompt_includes_graph_context(self, minimal_repo_map):
        from repoforge.prompts import skill_prompt

        module = minimal_repo_map["layers"]["main"]["modules"][0]
        fake_ctx = "## Module Dependencies\n**Depends on**: utils.py\n"
        system, user = skill_prompt(
            module, "main", minimal_repo_map,
            graph_context=fake_ctx,
        )
        assert "Module Dependencies" in user
        assert "Depends on" in user

    def test_layer_skill_prompt_includes_graph_context(self, minimal_repo_map):
        from repoforge.prompts import layer_skill_prompt

        layer = minimal_repo_map["layers"]["main"]
        fake_ctx = "## Dependency Summary\n**Modules**: 10\n"
        system, user = layer_skill_prompt(
            "main", layer, minimal_repo_map,
            graph_context=fake_ctx,
        )
        assert "Dependency Summary" in user

    def test_docs_architecture_gets_full_context(self, minimal_repo_map):
        from repoforge.docs_prompts import get_chapter_prompts

        full_ctx = "## Dependency Analysis\nFull graph here\n"
        short_ctx = "## Dependency Summary\nShort\n"
        chapters = get_chapter_prompts(
            minimal_repo_map, "English", "TestProject",
            graph_context=full_ctx,
            short_graph_context=short_ctx,
        )

        arch_ch = [c for c in chapters if c["file"] == "03-architecture.md"]
        assert len(arch_ch) == 1
        assert "Dependency Analysis" in arch_ch[0]["user"]
        assert "Full graph here" in arch_ch[0]["user"]

    def test_docs_non_arch_gets_short_context(self, minimal_repo_map):
        from repoforge.docs_prompts import get_chapter_prompts

        full_ctx = "## Dependency Analysis\nFull graph here\n"
        short_ctx = "## Dependency Summary\nShort version\n"
        chapters = get_chapter_prompts(
            minimal_repo_map, "English", "TestProject",
            graph_context=full_ctx,
            short_graph_context=short_ctx,
        )

        overview = [c for c in chapters if c["file"] == "01-overview.md"]
        assert len(overview) == 1
        assert "Dependency Summary" in overview[0]["user"]
        assert "Full graph here" not in overview[0]["user"]
