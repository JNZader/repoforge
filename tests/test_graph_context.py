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
    build_semantic_context,
    format_facts_section,
    format_snippets_section,
    build_module_facts_context,
)
from repoforge.facts import FactItem


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


# ---------------------------------------------------------------------------
# Semantic context: format_facts_section
# ---------------------------------------------------------------------------

class TestFormatFactsSection:
    def test_returns_empty_for_no_facts(self):
        assert format_facts_section([]) == ""

    def test_groups_by_fact_type(self):
        facts = [
            FactItem(fact_type="endpoint", value="GET /health", file="server.go", line=42, language="Go"),
            FactItem(fact_type="endpoint", value="POST /save", file="server.go", line=67, language="Go"),
            FactItem(fact_type="port", value="7437", file="server.go", line=75, language="Go"),
        ]
        result = format_facts_section(facts)
        assert "## Extracted Facts" in result
        assert "### HTTP Endpoints" in result
        assert "GET /health" in result
        assert "POST /save" in result
        assert "### Port Configuration" in result
        assert "7437" in result

    def test_includes_file_and_line(self):
        facts = [
            FactItem(fact_type="env_var", value="ENGRAM_PORT", file="main.go", line=80, language="Go"),
        ]
        result = format_facts_section(facts)
        assert "main.go:80" in result

    def test_all_fact_types_get_labels(self):
        """Each known fact type should have a human-readable label."""
        for ft in ("endpoint", "port", "version", "db_table", "cli_command", "env_var"):
            facts = [FactItem(fact_type=ft, value="test", file="f.go", line=1, language="Go")]
            result = format_facts_section(facts)
            # Should NOT just use the raw fact_type as heading
            assert f"### {ft}" not in result or ft == "version"


# ---------------------------------------------------------------------------
# Semantic context: format_snippets_section
# ---------------------------------------------------------------------------

class TestFormatSnippetsSection:
    def test_returns_empty_for_no_snippets(self):
        from repoforge.graph_context import CodeSnippet
        assert format_snippets_section([]) == ""

    def test_formats_code_blocks(self):
        from repoforge.graph_context import CodeSnippet
        snippets = [
            CodeSnippet(file="cmd/main.go", content="package main\nfunc main() {}", token_estimate=10, reason="entry_point"),
        ]
        result = format_snippets_section(snippets)
        assert "## Key Source Code" in result
        assert "```go" in result
        assert "cmd/main.go" in result
        assert "entry point" in result

    def test_detects_python_language(self):
        from repoforge.graph_context import CodeSnippet
        snippets = [
            CodeSnippet(file="app.py", content="def main(): pass", token_estimate=5, reason="most_connected"),
        ]
        result = format_snippets_section(snippets)
        assert "```python" in result


# ---------------------------------------------------------------------------
# Semantic context: build_semantic_context
# ---------------------------------------------------------------------------

class TestBuildSemanticContext:
    def test_returns_string_for_repoforge_project(self):
        """Semantic context on repoforge itself should produce non-empty output."""
        root = str(Path(__file__).parent.parent)
        from repoforge.scanner import scan_repo
        repo_map = scan_repo(root)
        all_files = [
            m["path"]
            for layer in repo_map["layers"].values()
            for m in layer.get("modules", [])
        ]
        result = build_semantic_context(root, all_files)
        # Should have at least graph context (repoforge has modules)
        assert result != ""
        assert "Dependency Analysis" in result

    def test_returns_empty_when_all_fail(self):
        """When root is invalid, graph fails, facts fail — return empty string."""
        result = build_semantic_context("/nonexistent/path", [])
        assert result == ""

    def test_includes_facts_when_available(self, sample_graph, tmp_path):
        """When facts are extractable, they appear in the output."""
        # Create a Go file with an endpoint pattern
        go_file = tmp_path / "server.go"
        go_file.write_text('package main\nfunc init() {\n  r.Get("/health", handler)\n}\n')

        result = build_semantic_context(
            str(tmp_path),
            ["server.go"],
            graph=sample_graph,
            include_snippets=False,
        )
        # Graph context should be present
        assert "Dependency Analysis" in result
        # Facts should be present (endpoint extracted)
        assert "Extracted Facts" in result
        assert "/health" in result

    def test_works_without_graph(self, tmp_path):
        """Even without a graph, facts should still be extracted."""
        go_file = tmp_path / "main.go"
        go_file.write_text('package main\nvar VERSION = "1.0.0"\n')

        result = build_semantic_context(
            str(tmp_path),
            ["main.go"],
            graph=None,
            include_snippets=False,
        )
        # No graph context, but version fact should appear
        assert "1.0.0" in result

    def test_include_snippets_false_skips_code(self, sample_graph, tmp_path):
        """include_snippets=False should omit the Key Source Code section."""
        result = build_semantic_context(
            str(tmp_path), [],
            graph=sample_graph,
            include_snippets=False,
        )
        assert "Key Source Code" not in result


# ---------------------------------------------------------------------------
# Semantic context: build_module_facts_context
# ---------------------------------------------------------------------------

class TestBuildModuleFactsContext:
    def test_returns_empty_for_nonexistent_file(self, tmp_path):
        result = build_module_facts_context(str(tmp_path), "nonexistent.go", [])
        assert result == ""

    def test_extracts_facts_from_specific_module(self, tmp_path):
        go_file = tmp_path / "server.go"
        go_file.write_text('package main\nfunc init() {\n  r.Get("/api/v1/users", handler)\n}\n')

        result = build_module_facts_context(str(tmp_path), "server.go", ["server.go"])
        assert "/api/v1/users" in result


# ---------------------------------------------------------------------------
# Graceful fallback: semantic context in prompts
# ---------------------------------------------------------------------------

class TestSemanticContextFallback:
    def test_docs_prompts_with_semantic_context(self, minimal_repo_map):
        """Docs prompts work with semantic context (facts + graph) injected."""
        from repoforge.docs_prompts import get_chapter_prompts

        semantic_ctx = "## Extracted Facts\n### Port Configuration\n- 7437 (server.go:75)\n\n## Dependency Analysis\nFull graph\n"
        facts_short = "## Extracted Facts\n### Port Configuration\n- 7437 (server.go:75)\n"

        chapters = get_chapter_prompts(
            minimal_repo_map, "English", "TestProject",
            graph_context=semantic_ctx,
            short_graph_context=facts_short,
        )
        assert len(chapters) > 0
        # Architecture chapter should have full semantic context
        arch = [c for c in chapters if c["file"] == "03-architecture.md"]
        assert len(arch) == 1
        assert "7437" in arch[0]["user"]
        assert "Dependency Analysis" in arch[0]["user"]

        # Other chapters get facts but not full graph
        overview = [c for c in chapters if c["file"] == "01-overview.md"]
        assert len(overview) == 1
        assert "7437" in overview[0]["user"]

    def test_skill_prompt_with_facts_context(self, minimal_repo_map):
        """Skill prompt works when facts context is injected."""
        from repoforge.prompts import skill_prompt

        module = minimal_repo_map["layers"]["main"]["modules"][0]
        facts_ctx = "## Extracted Facts\n### Environment Variables\n- ENGRAM_PORT (main.go:80)\n"
        system, user = skill_prompt(
            module, "main", minimal_repo_map,
            graph_context=facts_ctx,
        )
        assert "ENGRAM_PORT" in user

    def test_extracted_facts_rule_in_docs_system_prompt(self):
        """The docs system prompt should mention the Extracted Facts rule."""
        from repoforge.docs_prompts import _base_system
        system = _base_system("English")
        assert "Extracted Facts" in system
        assert "EXACT" in system

    def test_extracted_facts_rule_in_skill_system_prompt(self):
        """The skills system prompt should mention the Extracted Facts rule."""
        from repoforge.prompts import SKILL_SYSTEM, LAYER_SKILL_SYSTEM
        assert "Extracted Facts" in SKILL_SYSTEM
        assert "Extracted Facts" in LAYER_SKILL_SYSTEM
