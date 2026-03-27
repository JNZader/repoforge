"""
Intelligence Engine — optional enhanced analysis for RepoForge.

Provides build-file parsing, AST extraction (tree-sitter), graph ranking,
token-budgeted selection, and compressed export.

The build parser is always available (pure Python, no extra deps).
Tree-sitter features require: pip install repoforge-ai[intelligence]
"""

# Tree-sitter availability flag — checked once at import time
INTELLIGENCE_AVAILABLE = False
try:
    import tree_sitter  # noqa: F401
    INTELLIGENCE_AVAILABLE = True
except ImportError:
    pass

# Build parser is always available (no extra deps)
from .build_parser import BuildInfo, parse_build_files  # noqa: F401

__all__ = [
    "INTELLIGENCE_AVAILABLE",
    "BuildInfo",
    "parse_build_files",
]
