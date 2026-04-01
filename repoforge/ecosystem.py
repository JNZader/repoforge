"""Ecosystem utilities — package metadata, extras, plugin registry.

Provides introspection APIs for repoforge's capabilities,
installed extras, and available plugin modules.

Usage:
    from repoforge.ecosystem import get_package_metadata, get_plugin_registry
    meta = get_package_metadata()
    plugins = get_plugin_registry()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Package metadata
# ---------------------------------------------------------------------------


def get_package_metadata() -> dict:
    """Return repoforge package metadata."""
    try:
        from importlib.metadata import metadata
        meta = metadata("repoforge-ai")
        return {
            "name": meta["Name"],
            "version": meta["Version"],
            "description": meta["Summary"],
            "author": meta.get("Author", ""),
            "license": meta.get("License", ""),
            "homepage": meta.get("Home-page", ""),
        }
    except Exception:
        # Fallback for development installs
        from . import __version__
        return {
            "name": "repoforge-ai",
            "version": __version__,
            "description": "AI-powered code documentation generator",
        }


def get_available_extras() -> list[dict]:
    """Return list of available pip extras with their packages."""
    return [
        {
            "name": "dev",
            "description": "Development tools (pytest, ruff, mypy)",
            "packages": ["pytest>=7.0", "pytest-cov", "ruff", "mypy>=1.0"],
            "install": "pip install repoforge-ai[dev]",
        },
        {
            "name": "intelligence",
            "description": "AST analysis via tree-sitter (6 languages)",
            "packages": ["tree-sitter>=0.23", "tree-sitter-language-pack>=1.0"],
            "install": "pip install repoforge-ai[intelligence]",
        },
        {
            "name": "all",
            "description": "All optional dependencies",
            "packages": [
                "pytest>=7.0", "pytest-cov", "ruff", "mypy>=1.0",
                "tree-sitter>=0.23", "tree-sitter-language-pack>=1.0",
            ],
            "install": "pip install repoforge-ai[all]",
        },
    ]


# ---------------------------------------------------------------------------
# Plugin registry
# ---------------------------------------------------------------------------


@dataclass
class PluginInfo:
    """Metadata for a repoforge module/capability."""
    name: str
    description: str
    module_path: str
    category: str = "core"


def get_plugin_registry() -> list[PluginInfo]:
    """Return registry of all repoforge capabilities/modules."""
    return [
        PluginInfo(
            name="scoring",
            description="Rule-based documentation quality scoring (4 dimensions)",
            module_path="repoforge.scoring",
            category="quality",
        ),
        PluginInfo(
            name="refinement",
            description="Generate → score → critique → regenerate loop",
            module_path="repoforge.refinement",
            category="quality",
        ),
        PluginInfo(
            name="cache",
            description="Content hashing, repo snapshots, LLM response caching",
            module_path="repoforge.cache",
            category="performance",
        ),
        PluginInfo(
            name="renderers",
            description="Output format renderers (markdown, llms.txt, JSON)",
            module_path="repoforge.renderers",
            category="output",
        ),
        PluginInfo(
            name="personas",
            description="Audience-adaptive prompts (beginner, architect, etc.)",
            module_path="repoforge.personas",
            category="generation",
        ),
        PluginInfo(
            name="profiles",
            description="Config profiles for project types (fastapi, cli, library)",
            module_path="repoforge.profiles",
            category="configuration",
        ),
        PluginInfo(
            name="knowledge",
            description="Architecture pattern detection + Mermaid diagrams",
            module_path="repoforge.knowledge",
            category="analysis",
        ),
        PluginInfo(
            name="analysis",
            description="Dead code detection, complexity analysis, example extraction",
            module_path="repoforge.analysis",
            category="analysis",
        ),
        PluginInfo(
            name="ci",
            description="Git diff detection, doc drift, quality gate",
            module_path="repoforge.ci",
            category="integration",
        ),
        PluginInfo(
            name="mcp_tools",
            description="MCP tool/resource definitions for AI agent integration",
            module_path="repoforge.mcp_tools",
            category="integration",
        ),
        PluginInfo(
            name="watch",
            description="File watcher for incremental regeneration",
            module_path="repoforge.watch",
            category="integration",
        ),
        PluginInfo(
            name="generators",
            description="Changelog, API reference, onboarding guide generators",
            module_path="repoforge.generators",
            category="generation",
        ),
        PluginInfo(
            name="style",
            description="Style enforcement rules for generated docs",
            module_path="repoforge.style",
            category="quality",
        ),
        PluginInfo(
            name="performance",
            description="Cost estimation, rate limiting, batch execution",
            module_path="repoforge.performance",
            category="performance",
        ),
        PluginInfo(
            name="symbol_linker",
            description="Cross-file type resolution and relationship tracking",
            module_path="repoforge.intelligence.symbol_linker",
            category="analysis",
        ),
        PluginInfo(
            name="dep_health",
            description="Dependency health analysis — tree depth, duplicates, licenses, outdated",
            module_path="repoforge.dep_health",
            category="analysis",
        ),
    ]
