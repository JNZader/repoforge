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
# AST types are always importable (no native deps)
from .ast_extractor import ASTLanguageExtractor, ASTSymbol  # noqa: F401

# Token-budgeted context selection (always available)
from .budget import ContextItem, select_context  # noqa: F401
from .build_parser import BuildInfo, parse_build_files  # noqa: F401

# Source code compression (tree-sitter for full, fallback for basic)
from .compressor import compress_batch, compress_file, compression_stats  # noqa: F401

# Pre-digested documentation chunks (always available)
from .doc_chunks import (  # noqa: F401
    build_all_ast_symbols,
    chunk_architecture,
    chunk_cli_commands,
    chunk_data_models,
    chunk_endpoints,
    chunk_mcp_tools,
    chunk_module_summary,
)

# Registry convenience functions (gracefully return empty when tree-sitter unavailable)
from .extractor_registry import (  # noqa: F401
    ast_extract_endpoints,
    ast_extract_schemas,
    ast_extract_symbols,
    get_ast_registry,
)

# PageRank scoring (always available — no tree-sitter needed)
from .ranker import pagerank, rank_files  # noqa: F401

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
    "pagerank",
    "rank_files",
    "select_context",
    "ContextItem",
    "compress_file",
    "compress_batch",
    "compression_stats",
    "chunk_endpoints",
    "chunk_data_models",
    "chunk_mcp_tools",
    "chunk_cli_commands",
    "chunk_architecture",
    "chunk_module_summary",
    "chunk_type_relationships",
    "build_all_ast_symbols",
    "SymbolLinker",
]
