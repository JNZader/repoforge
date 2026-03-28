"""MCP tool and resource definitions for repoforge.

Exports JSON Schema definitions that describe repoforge's capabilities
as MCP tools. These can be consumed by any MCP server implementation
(mcp-llm-bridge, Claude Desktop, custom servers).

Usage:
    from repoforge.mcp_tools import get_mcp_tool_definitions
    tools = get_mcp_tool_definitions()
    # Pass to MCP server's tool registration
"""

from __future__ import annotations


def get_mcp_tool_definitions() -> list[dict]:
    """Return MCP tool definitions for repoforge capabilities."""
    return [
        {
            "name": "repoforge_generate_docs",
            "description": (
                "Generate technical documentation for a code repository. "
                "Produces a Docsify-ready docs/ folder with overview, architecture, "
                "API reference, and more. Supports multiple languages and personas."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "working_dir": {
                        "type": "string",
                        "description": "Path to the repository root",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Output directory for generated docs",
                        "default": "docs",
                    },
                    "language": {
                        "type": "string",
                        "description": "Documentation language",
                        "default": "English",
                        "enum": [
                            "English", "Spanish", "French", "German",
                            "Portuguese", "Chinese", "Japanese", "Korean",
                        ],
                    },
                    "persona": {
                        "type": "string",
                        "description": "Target audience persona",
                        "enum": ["beginner", "contributor", "architect", "api-consumer"],
                    },
                    "model": {
                        "type": "string",
                        "description": "LLM model to use (e.g., gpt-4o-mini, claude-haiku-3-5)",
                    },
                    "facts_only": {
                        "type": "boolean",
                        "description": "Use facts-only mode for reduced token usage",
                        "default": False,
                    },
                },
                "required": ["working_dir"],
            },
        },
        {
            "name": "repoforge_score",
            "description": (
                "Score the quality of generated documentation across 4 dimensions: "
                "structure, completeness, code quality, and clarity. "
                "Returns per-file scores with PASS/WARN/FAIL grades."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "docs_dir": {
                        "type": "string",
                        "description": "Path to the docs directory to score",
                    },
                    "threshold": {
                        "type": "number",
                        "description": "Minimum score to pass (0.0-1.0)",
                        "default": 0.7,
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format",
                        "enum": ["table", "json"],
                        "default": "table",
                    },
                },
                "required": ["docs_dir"],
            },
        },
        {
            "name": "repoforge_graph",
            "description": (
                "Build a code knowledge graph from a repository. "
                "Detects architecture patterns (layered, multi-layer, hub-spoke, circular deps) "
                "and generates Mermaid dependency diagrams."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "working_dir": {
                        "type": "string",
                        "description": "Path to the repository root",
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format",
                        "enum": ["mermaid", "json", "summary"],
                        "default": "summary",
                    },
                },
                "required": ["working_dir"],
            },
        },
        {
            "name": "repoforge_scan",
            "description": (
                "Security scan generated documentation output for sensitive data, "
                "credential leaks, and unsafe patterns."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "target_dir": {
                        "type": "string",
                        "description": "Directory to scan",
                    },
                    "fail_on": {
                        "type": "string",
                        "description": "Minimum severity to fail on",
                        "enum": ["critical", "high", "medium", "low"],
                        "default": "high",
                    },
                },
                "required": ["target_dir"],
            },
        },
        {
            "name": "repoforge_drift",
            "description": (
                "Check if generated documentation is stale relative to source code. "
                "Compares source file hashes against docs state."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "working_dir": {
                        "type": "string",
                        "description": "Path to the repository root",
                    },
                    "docs_dir": {
                        "type": "string",
                        "description": "Path to docs directory",
                        "default": "docs",
                    },
                },
                "required": ["working_dir"],
            },
        },
    ]


def get_mcp_resource_definitions() -> list[dict]:
    """Return MCP resource definitions for repoforge outputs."""
    return [
        {
            "uri": "repoforge://docs/{project}",
            "name": "Generated Documentation",
            "description": "Generated documentation chapters for a project",
            "mimeType": "text/markdown",
        },
        {
            "uri": "repoforge://docs/{project}/llms.txt",
            "name": "LLMs.txt",
            "description": "AI-consumable documentation summary (llms.txt standard)",
            "mimeType": "text/plain",
        },
        {
            "uri": "repoforge://graph/{project}",
            "name": "Code Knowledge Graph",
            "description": "Dependency graph with architecture pattern analysis",
            "mimeType": "application/json",
        },
        {
            "uri": "repoforge://scores/{project}",
            "name": "Quality Scores",
            "description": "Documentation quality scores per chapter",
            "mimeType": "application/json",
        },
    ]
