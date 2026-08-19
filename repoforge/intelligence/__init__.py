"""
Intelligence Engine — optional enhanced analysis for RepoForge.

Provides build-file parsing, AST extraction (tree-sitter), graph ranking,
token-budgeted selection, and compressed export.

The build parser is always available (pure Python, no extra deps).
Tree-sitter features require: pip install repoforge-ai[intelligence]
"""

from ._availability import INTELLIGENCE_AVAILABLE as INTELLIGENCE_AVAILABLE

# Build parser is always available (no extra deps)
# AST types are always importable (no native deps)
from .ast_extractor import ASTLanguageExtractor as ASTLanguageExtractor
from .ast_extractor import ASTSymbol as ASTSymbol

# Token-budgeted context selection (always available)
from .budget import ContextItem as ContextItem
from .budget import select_context as select_context
from .build_parser import BuildInfo as BuildInfo
from .build_parser import parse_build_files as parse_build_files

# Source code compression (tree-sitter for full, fallback for basic)
from .compressor import compress_batch as compress_batch
from .compressor import compress_file as compress_file
from .compressor import compression_stats as compression_stats

# Pre-digested documentation chunks (always available)
from .doc_chunks import (
    build_all_ast_symbols,
    chunk_architecture,
    chunk_cli_commands,
    chunk_data_models,
    chunk_endpoints,
    chunk_mcp_tools,
    chunk_module_summary,
)

# Registry convenience functions (gracefully return empty when tree-sitter unavailable)
from .extractor_registry import (
    ast_extract_endpoints,
    ast_extract_schemas,
    ast_extract_symbols,
    get_ast_registry,
)

# PageRank scoring (always available — no tree-sitter needed)
from .ranker import pagerank as pagerank
from .ranker import rank_files as rank_files

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
