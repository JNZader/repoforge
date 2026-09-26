"""README and the MCP server name the same tools, and the cost table matches."""

import asyncio
from pathlib import Path

from repoforge.mcp_server import list_tools

ROOT = Path(__file__).resolve().parents[1]
REGISTERED_TOOLS = (
    "repoforge_score",
    "repoforge_graph",
    "repoforge_changelog",
    "repoforge_drift",
    "repoforge_analyze",
    "repoforge_context",
)


def test_list_tools_returns_the_registered_names():
    tools = asyncio.run(list_tools())
    assert tuple(tool.name for tool in tools) == REGISTERED_TOOLS


def test_readmes_match_registered_tools_and_cost():
    for name in ("README.md", "README.es.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        mcp_heading = "## MCP Server" if name == "README.md" else "## Servidor MCP"
        mcp_section = text.split(mcp_heading, 1)[1].split("## ", 1)[0]
        for tool in REGISTERED_TOOLS:
            assert tool in mcp_section
        assert "repoforge_generate_docs" not in text
        assert "repoforge_scan" not in text
        assert "8x" not in text
        assert "skills-from-docs`, `index`" not in text
        assert "`docs`, `skills`, `index`" in text
        assert "for `analyze`, `slice`" not in text
        assert "para `analyze`, `slice`" not in text
        assert "needs [intelligence] extra" not in text
        assert "necesita el extra [intelligence]" not in text
