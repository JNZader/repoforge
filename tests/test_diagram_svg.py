"""Tests for diagram_svg module — items #22 and #23."""

from pathlib import Path

import pytest

from repoforge.diagram_svg import (
    DEFAULT_SHAPE_COLORS,
    DEFAULT_SHAPE_RULES,
    DiagramStyle,
    generate_svg_diagram,
)
from repoforge.graph import CodeGraph, Edge, Node

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_graph():
    """Create a simple CodeGraph for SVG generation."""
    graph = CodeGraph()
    graph.add_node(Node(
        id="src/service.py", name="service",
        node_type="module", file_path="src/service.py",
        exports=["get_user", "create_user"],
    ))
    graph.add_node(Node(
        id="src/models.py", name="models",
        node_type="module", file_path="src/models.py",
        exports=["User", "Order"],
    ))
    graph.add_node(Node(
        id="src/api.py", name="api",
        node_type="module", file_path="src/api.py",
        exports=["handler"],
    ))
    graph.add_edge(Edge(
        source="src/service.py", target="src/models.py",
        edge_type="imports",
    ))
    graph.add_edge(Edge(
        source="src/api.py", target="src/service.py",
        edge_type="imports",
    ))
    return graph


@pytest.fixture
def semantic_graph():
    """Create a graph with semantic node names for style testing."""
    graph = CodeGraph()
    graph.add_node(Node(
        id="agent.py", name="agent",
        node_type="module", file_path="agent.py",
    ))
    graph.add_node(Node(
        id="store.py", name="store",
        node_type="module", file_path="store.py",
    ))
    graph.add_node(Node(
        id="router.py", name="router",
        node_type="module", file_path="router.py",
    ))
    graph.add_node(Node(
        id="utils.py", name="utils",
        node_type="module", file_path="utils.py",
    ))
    graph.add_node(Node(
        id="cli.py", name="cli",
        node_type="module", file_path="cli.py",
    ))
    return graph


# ---------------------------------------------------------------------------
# Style system tests (#23)
# ---------------------------------------------------------------------------


class TestDiagramStyle:
    def test_default_shape_for_unknown(self):
        style = DiagramStyle()
        assert style.get_shape("random_module") == "rectangle"

    def test_agent_gets_hexagon(self):
        style = DiagramStyle()
        assert style.get_shape("agent_handler") == "hexagon"

    def test_store_gets_cylinder(self):
        style = DiagramStyle()
        assert style.get_shape("data_store") == "cylinder"

    def test_router_gets_diamond(self):
        style = DiagramStyle()
        assert style.get_shape("request_router") == "diamond"

    def test_util_gets_rounded(self):
        style = DiagramStyle()
        assert style.get_shape("string_utils") == "rounded"

    def test_cli_gets_ellipse(self):
        style = DiagramStyle()
        assert style.get_shape("cli") == "ellipse"

    def test_file_path_also_checked(self):
        style = DiagramStyle()
        # Even if name is generic, file path with "agent" should match
        assert style.get_shape("main", "agents/main.py") == "hexagon"

    def test_custom_shape_rules(self):
        style = DiagramStyle(
            shape_rules={"custom": "diamond"},
        )
        assert style.get_shape("custom_thing") == "diamond"
        # Unknown still gets rectangle
        assert style.get_shape("other") == "rectangle"

    def test_get_color(self):
        style = DiagramStyle()
        color = style.get_color("hexagon")
        assert color == DEFAULT_SHAPE_COLORS["hexagon"]

    def test_get_color_unknown_shape(self):
        style = DiagramStyle()
        color = style.get_color("nonexistent")
        # Falls back to rectangle color
        assert color == DEFAULT_SHAPE_COLORS["rectangle"]


# ---------------------------------------------------------------------------
# SVG generation tests (#22)
# ---------------------------------------------------------------------------


class TestGenerateSvgDiagram:
    def test_produces_valid_svg(self, simple_graph):
        svg = generate_svg_diagram(simple_graph)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        assert "xmlns" in svg

    def test_contains_nodes(self, simple_graph):
        svg = generate_svg_diagram(simple_graph)
        assert "service" in svg
        assert "models" in svg
        assert "api" in svg

    def test_contains_edges(self, simple_graph):
        svg = generate_svg_diagram(simple_graph)
        # Should have arrow paths
        assert "arrowhead" in svg

    def test_contains_legend(self, simple_graph):
        style = DiagramStyle(show_legend=True)
        svg = generate_svg_diagram(simple_graph, style)
        assert "Legend" in svg
        assert "Agent" in svg
        assert "Store" in svg

    def test_no_legend(self, simple_graph):
        style = DiagramStyle(show_legend=False)
        svg = generate_svg_diagram(simple_graph, style)
        assert "Legend" not in svg

    def test_custom_title(self, simple_graph):
        svg = generate_svg_diagram(simple_graph, title="My Project")
        assert "My Project" in svg

    def test_empty_graph(self):
        graph = CodeGraph()
        svg = generate_svg_diagram(graph)
        assert "No modules detected" in svg

    def test_semantic_shapes_applied(self, semantic_graph):
        style = DiagramStyle()
        svg = generate_svg_diagram(semantic_graph, style)
        # hexagon for agent (polygon), cylinder (ellipse + rect)
        assert "polygon" in svg  # hexagon or diamond
        assert "ellipse" in svg  # cylinder or ellipse shape

    def test_max_nodes_limits_output(self):
        graph = CodeGraph()
        for i in range(100):
            graph.add_node(Node(
                id=f"mod{i}.py", name=f"mod{i}",
                node_type="module", file_path=f"mod{i}.py",
            ))
        svg = generate_svg_diagram(graph, max_nodes=10)
        # Should have far fewer text elements than 100
        count = svg.count("<text")
        # Legend has ~7 text elements, plus max 10 nodes + directory labels
        assert count < 30

    def test_custom_colors(self, simple_graph):
        style = DiagramStyle(
            bg_color="#ffffff",
            text_color="#000000",
            edge_color="#ff0000",
        )
        svg = generate_svg_diagram(simple_graph, style)
        assert "#ffffff" in svg
        assert "#000000" in svg

    def test_html_escaping(self):
        """Node names with special chars should be escaped."""
        graph = CodeGraph()
        graph.add_node(Node(
            id="test.py", name='test<script>',
            node_type="module", file_path="test.py",
        ))
        svg = generate_svg_diagram(graph)
        assert "<script>" not in svg
        assert "&lt;script&gt;" in svg
