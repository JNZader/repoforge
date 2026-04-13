"""
diagram_svg.py — Auto-generated architecture diagrams in SVG format.

Generates publication-ready SVG diagrams from the code dependency graph.
Not Mermaid — actual SVG with semantic shapes, layout, and styling.

Includes a configurable style system (#23) with semantic shape vocabulary:
  - hexagon  → agents, orchestrators
  - cylinder → stores, databases
  - rectangle → services, modules (default)
  - rounded  → utilities, helpers
  - diamond  → decision points, routers
  - ellipse  → entry points, APIs

Entry points:
  - generate_svg_diagram(graph, style): returns SVG string
  - DiagramStyle: configurable style with shape/color mapping
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass, field

from .graph import CodeGraph

# ---------------------------------------------------------------------------
# Style system (#23)
# ---------------------------------------------------------------------------

# Default semantic shape rules: pattern → shape
# Patterns are matched against node name and file path (case-insensitive)
DEFAULT_SHAPE_RULES: dict[str, str] = {
    "agent": "hexagon",
    "orchestrat": "hexagon",
    "coordinator": "hexagon",
    "store": "cylinder",
    "database": "cylinder",
    "db": "cylinder",
    "cache": "cylinder",
    "repository": "cylinder",
    "repo": "cylinder",
    "service": "rectangle",
    "controller": "rectangle",
    "handler": "rectangle",
    "middleware": "rectangle",
    "util": "rounded",
    "helper": "rounded",
    "common": "rounded",
    "shared": "rounded",
    "lib": "rounded",
    "router": "diamond",
    "dispatch": "diamond",
    "resolver": "diamond",
    "main": "ellipse",
    "cli": "ellipse",
    "app": "ellipse",
    "index": "ellipse",
    "entry": "ellipse",
    "api": "ellipse",
    "test": "rounded",
}

# Default color palette per shape
DEFAULT_SHAPE_COLORS: dict[str, str] = {
    "hexagon": "#6366f1",    # indigo — agents
    "cylinder": "#0891b2",   # cyan — stores
    "rectangle": "#2563eb",  # blue — services
    "rounded": "#7c3aed",    # violet — utilities
    "diamond": "#d97706",    # amber — routers
    "ellipse": "#059669",    # emerald — entry points
}

DEFAULT_TEXT_COLOR = "#ffffff"
DEFAULT_EDGE_COLOR = "#94a3b8"  # slate-400
DEFAULT_BG_COLOR = "#0f172a"    # slate-900


@dataclass
class DiagramStyle:
    """Configurable style for SVG diagrams.

    Attributes:
        shape_rules: Mapping of keyword patterns to shape names.
        shape_colors: Mapping of shape names to fill colors.
        text_color: Color for text labels.
        edge_color: Color for dependency arrows.
        bg_color: Background color (empty string for transparent).
        node_width: Default node width in pixels.
        node_height: Default node height in pixels.
        font_size: Font size in pixels.
        font_family: Font family string.
        padding: Padding between nodes.
        show_legend: Whether to render a shape legend.
    """

    shape_rules: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SHAPE_RULES))
    shape_colors: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SHAPE_COLORS))
    text_color: str = DEFAULT_TEXT_COLOR
    edge_color: str = DEFAULT_EDGE_COLOR
    bg_color: str = DEFAULT_BG_COLOR
    node_width: int = 160
    node_height: int = 50
    font_size: int = 12
    font_family: str = "system-ui, -apple-system, sans-serif"
    padding: int = 40
    show_legend: bool = True

    def get_shape(self, node_name: str, file_path: str = "") -> str:
        """Determine the shape for a node based on its name/path."""
        text = (node_name + " " + file_path).lower()
        for pattern, shape in self.shape_rules.items():
            if pattern in text:
                return shape
        return "rectangle"

    def get_color(self, shape: str) -> str:
        """Get the fill color for a shape."""
        return self.shape_colors.get(shape, self.shape_colors.get("rectangle", "#2563eb"))


# ---------------------------------------------------------------------------
# SVG shape renderers
# ---------------------------------------------------------------------------


def _svg_rectangle(x: float, y: float, w: float, h: float, fill: str, rx: int = 4) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'rx="{rx}" ry="{rx}" fill="{fill}" />'
    )


def _svg_rounded(x: float, y: float, w: float, h: float, fill: str) -> str:
    return _svg_rectangle(x, y, w, h, fill, rx=int(h / 2))


def _svg_ellipse(cx: float, cy: float, rx: float, ry: float, fill: str) -> str:
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" />'


def _svg_hexagon(cx: float, cy: float, w: float, h: float, fill: str) -> str:
    """Flat-top hexagon."""
    hw = w / 2
    hh = h / 2
    inset = w * 0.15
    points = [
        (cx - hw + inset, cy - hh),
        (cx + hw - inset, cy - hh),
        (cx + hw, cy),
        (cx + hw - inset, cy + hh),
        (cx - hw + inset, cy + hh),
        (cx - hw, cy),
    ]
    pts = " ".join(f"{px},{py}" for px, py in points)
    return f'<polygon points="{pts}" fill="{fill}" />'


def _svg_cylinder(x: float, y: float, w: float, h: float, fill: str) -> str:
    """Cylinder shape (rectangle with ellipses top/bottom)."""
    ry = 8  # ellipse radius for top/bottom
    body_h = h - ry * 2
    parts = [
        # Body
        f'<rect x="{x}" y="{y + ry}" width="{w}" height="{body_h}" fill="{fill}" />',
        # Bottom ellipse
        f'<ellipse cx="{x + w / 2}" cy="{y + h - ry}" rx="{w / 2}" ry="{ry}" fill="{fill}" />',
        # Top ellipse (slightly darker)
        f'<ellipse cx="{x + w / 2}" cy="{y + ry}" rx="{w / 2}" ry="{ry}" fill="{fill}" opacity="0.8" />',
    ]
    return "\n    ".join(parts)


def _svg_diamond(cx: float, cy: float, w: float, h: float, fill: str) -> str:
    hw = w / 2
    hh = h / 2
    points = [
        (cx, cy - hh),
        (cx + hw, cy),
        (cx, cy + hh),
        (cx - hw, cy),
    ]
    pts = " ".join(f"{px},{py}" for px, py in points)
    return f'<polygon points="{pts}" fill="{fill}" />'


def _render_shape(
    shape: str,
    x: float, y: float,
    w: float, h: float,
    fill: str,
) -> str:
    """Render a shape centered at the given position."""
    cx = x + w / 2
    cy = y + h / 2

    if shape == "hexagon":
        return _svg_hexagon(cx, cy, w, h, fill)
    elif shape == "cylinder":
        return _svg_cylinder(x, y, w, h, fill)
    elif shape == "diamond":
        return _svg_diamond(cx, cy, w * 1.2, h * 1.2, fill)
    elif shape == "ellipse":
        return _svg_ellipse(cx, cy, w / 2, h / 2, fill)
    elif shape == "rounded":
        return _svg_rounded(x, y, w, h, fill)
    else:
        return _svg_rectangle(x, y, w, h, fill)


# ---------------------------------------------------------------------------
# Layout engine (simple grid/layered)
# ---------------------------------------------------------------------------


def _compute_layout(
    graph: CodeGraph,
    style: DiagramStyle,
    max_nodes: int = 50,
) -> dict[str, tuple[float, float]]:
    """Compute node positions using a simple layered layout.

    Groups modules by directory, arranges directories in columns,
    and modules within each directory in rows.

    Returns: {node_id: (x, y)} positions.
    """
    from pathlib import Path

    module_nodes = [n for n in graph.nodes if n.node_type == "module"]

    # Rank by connection count for priority
    connections: dict[str, int] = {}
    for e in graph.edges:
        if e.edge_type in ("imports", "depends_on"):
            connections[e.source] = connections.get(e.source, 0) + 1
            connections[e.target] = connections.get(e.target, 0) + 1

    ranked = sorted(module_nodes, key=lambda n: connections.get(n.id, 0), reverse=True)
    selected = ranked[:max_nodes]

    # Group by parent directory
    by_dir: dict[str, list] = {}
    for n in selected:
        parent = str(Path(n.file_path).parent) if n.file_path else "root"
        parent = parent if parent != "." else "root"
        by_dir.setdefault(parent, []).append(n)

    positions: dict[str, tuple[float, float]] = {}
    w = style.node_width
    h = style.node_height
    pad = style.padding

    col_x = pad
    for dir_name in sorted(by_dir.keys()):
        nodes = by_dir[dir_name]
        row_y = pad + 30  # leave room for directory label

        for n in nodes:
            positions[n.id] = (col_x, row_y)
            row_y += h + pad

        col_x += w + pad * 2

    return positions


# ---------------------------------------------------------------------------
# SVG edge rendering
# ---------------------------------------------------------------------------


def _render_edge(
    x1: float, y1: float,
    x2: float, y2: float,
    color: str,
    node_w: float,
    node_h: float,
) -> str:
    """Render a curved arrow between two node centers."""
    # Source: bottom center, Target: top center
    sx = x1 + node_w / 2
    sy = y1 + node_h
    tx = x2 + node_w / 2
    ty = y2

    # Control point for curve
    mid_y = (sy + ty) / 2
    dx = tx - sx

    # Simple bezier curve
    path = f"M {sx},{sy} C {sx},{mid_y} {tx},{mid_y} {tx},{ty}"

    return (
        f'<path d="{path}" fill="none" stroke="{color}" '
        f'stroke-width="1.5" marker-end="url(#arrowhead)" opacity="0.6" />'
    )


# ---------------------------------------------------------------------------
# Legend renderer
# ---------------------------------------------------------------------------


def _render_legend(style: DiagramStyle, x: float, y: float) -> str:
    """Render a shape legend at the given position."""
    legend_items = [
        ("hexagon", "Agent / Orchestrator"),
        ("cylinder", "Store / Database"),
        ("rectangle", "Service / Module"),
        ("rounded", "Utility / Helper"),
        ("diamond", "Router / Dispatcher"),
        ("ellipse", "Entry Point / API"),
    ]

    parts = [f'<g transform="translate({x},{y})">']
    parts.append(
        f'<text x="0" y="0" font-family="{style.font_family}" '
        f'font-size="{style.font_size}" fill="{style.text_color}" '
        f'font-weight="bold">Legend</text>'
    )

    item_y = 16
    for shape, label in legend_items:
        color = style.get_color(shape)
        shape_svg = _render_shape(shape, 0, item_y - 8, 24, 16, color)
        parts.append(f"  {shape_svg}")
        parts.append(
            f'  <text x="32" y="{item_y + 4}" font-family="{style.font_family}" '
            f'font-size="{style.font_size - 2}" fill="{style.text_color}" '
            f'opacity="0.8">{html.escape(label)}</text>'
        )
        item_y += 22

    parts.append("</g>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main SVG generator
# ---------------------------------------------------------------------------


def generate_svg_diagram(
    graph: CodeGraph,
    style: DiagramStyle | None = None,
    *,
    max_nodes: int = 50,
    title: str = "Architecture Diagram",
) -> str:
    """Generate a publication-ready SVG diagram from a CodeGraph.

    Args:
        graph: The CodeGraph to visualize.
        style: Optional DiagramStyle configuration.
        max_nodes: Maximum nodes to display.
        title: Diagram title.

    Returns:
        Complete SVG string.
    """
    if style is None:
        style = DiagramStyle()

    positions = _compute_layout(graph, style, max_nodes=max_nodes)
    if not positions:
        return _empty_svg(style, title)

    module_nodes = {n.id: n for n in graph.nodes if n.node_type == "module"}
    visible_ids = set(positions.keys())

    # Calculate canvas size
    max_x = max(x + style.node_width for x, _y in positions.values()) + style.padding
    max_y = max(_y + style.node_height for _x, _y in positions.values()) + style.padding

    # Add space for legend
    legend_width = 200 if style.show_legend else 0
    canvas_w = max_x + legend_width + style.padding
    canvas_h = max(max_y + style.padding, 300)

    # Add space for title
    title_offset = 40
    canvas_h += title_offset

    parts: list[str] = []

    # SVG header
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" '
        f'width="{canvas_w}" height="{canvas_h}">'
    )

    # Defs (arrowhead marker)
    parts.append("  <defs>")
    parts.append(
        f'    <marker id="arrowhead" markerWidth="10" markerHeight="7" '
        f'refX="10" refY="3.5" orient="auto">'
    )
    parts.append(f'      <polygon points="0 0, 10 3.5, 0 7" fill="{style.edge_color}" />')
    parts.append("    </marker>")
    parts.append("  </defs>")

    # Background
    if style.bg_color:
        parts.append(
            f'  <rect width="100%" height="100%" fill="{style.bg_color}" />'
        )

    # Title
    parts.append(
        f'  <text x="{style.padding}" y="{style.padding}" '
        f'font-family="{style.font_family}" font-size="{style.font_size + 4}" '
        f'fill="{style.text_color}" font-weight="bold">'
        f'{html.escape(title)}</text>'
    )

    # Shift everything down for title
    parts.append(f'  <g transform="translate(0,{title_offset})">')

    # Render edges first (behind nodes)
    for e in graph.edges:
        if e.edge_type == "contains":
            continue
        if e.source in visible_ids and e.target in visible_ids:
            sx, sy = positions[e.source]
            tx, ty = positions[e.target]
            edge_svg = _render_edge(
                sx, sy, tx, ty,
                style.edge_color,
                style.node_width,
                style.node_height,
            )
            parts.append(f"    {edge_svg}")

    # Group nodes by directory for subgraph labels
    from pathlib import Path as _Path
    by_dir: dict[str, list[str]] = {}
    for nid in visible_ids:
        node = module_nodes.get(nid)
        if node:
            parent = str(_Path(node.file_path).parent) if node.file_path else "root"
            parent = parent if parent != "." else "root"
            by_dir.setdefault(parent, []).append(nid)

    # Render directory labels
    for dir_name, node_ids in sorted(by_dir.items()):
        if node_ids:
            first_x, first_y = positions[node_ids[0]]
            parts.append(
                f'    <text x="{first_x}" y="{first_y - 8}" '
                f'font-family="{style.font_family}" font-size="{style.font_size - 1}" '
                f'fill="{style.text_color}" opacity="0.5" font-weight="bold">'
                f'{html.escape(dir_name)}</text>'
            )

    # Render nodes
    for nid, (x, y) in positions.items():
        node = module_nodes.get(nid)
        if not node:
            continue

        shape = style.get_shape(node.name, node.file_path)
        color = style.get_color(shape)
        shape_svg = _render_shape(shape, x, y, style.node_width, style.node_height, color)

        # Truncate label to fit
        label = node.name
        max_chars = style.node_width // (style.font_size * 0.6)
        if len(label) > max_chars:
            label = label[:int(max_chars) - 1] + "…"

        parts.append(f"    {shape_svg}")
        parts.append(
            f'    <text x="{x + style.node_width / 2}" y="{y + style.node_height / 2 + 4}" '
            f'text-anchor="middle" font-family="{style.font_family}" '
            f'font-size="{style.font_size}" fill="{style.text_color}">'
            f'{html.escape(label)}</text>'
        )

    # Legend
    if style.show_legend:
        legend_svg = _render_legend(style, max_x + style.padding, style.padding)
        parts.append(f"    {legend_svg}")

    parts.append("  </g>")
    parts.append("</svg>")

    return "\n".join(parts)


def _empty_svg(style: DiagramStyle, title: str) -> str:
    """Generate an empty SVG with a 'no data' message."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 100" '
        f'width="400" height="100">\n'
        f'  <rect width="100%" height="100%" fill="{style.bg_color}" />\n'
        f'  <text x="200" y="50" text-anchor="middle" '
        f'font-family="{style.font_family}" font-size="{style.font_size}" '
        f'fill="{style.text_color}">No modules detected for: '
        f'{html.escape(title)}</text>\n'
        f"</svg>"
    )
