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

# AST types are always importable (no native deps)
from .ast_extractor import ASTSymbol, ASTLanguageExtractor  # noqa: F401

# Registry convenience functions (gracefully return empty when tree-sitter unavailable)
from .extractor_registry import (  # noqa: F401
    get_ast_registry,
    ast_extract_symbols,
    ast_extract_endpoints,
    ast_extract_schemas,
)

__all__ = [
    "INTELLIGENCE_AVAILABLE",
    "BuildInfo",
    "parse_build_files",
    "ASTSymbol",
    "ASTLanguageExtractor",
    "get_ast_registry",
    "ast_extract_symbols",
    "ast_extract_endpoints",
    "ast_extract_schemas",
]
