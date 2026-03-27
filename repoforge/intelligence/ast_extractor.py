"""
AST Extractor Framework — tree-sitter based code analysis.

Provides enriched symbol extraction using tree-sitter parsers.
Each language has its own extractor implementing ASTLanguageExtractor.
Falls back gracefully when tree-sitter is not installed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..facts import FactItem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enriched symbol data
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ASTSymbol:
    """A code symbol extracted via tree-sitter AST parsing.

    Richer than ExportInfo — includes signatures, parameters, return types,
    docstrings, and source location. Used for intelligent context selection.
    """

    name: str
    """Symbol name (e.g., 'New', 'UserService', 'process')."""

    kind: str
    """Symbol kind: 'function', 'class', 'struct', 'method', 'interface',
    'type', 'constant', 'variable', 'enum', 'trait', 'schema'."""

    signature: str
    """Full signature, e.g. 'func New(store *Store, port int) *Server'."""

    params: list[str] = field(default_factory=list)
    """Parameter list, e.g. ['store *Store', 'port int']."""

    return_type: str | None = None
    """Return type if applicable, e.g. '*Server', 'dict', 'Promise<User>'."""

    docstring: str | None = None
    """First line of docstring/comment, if present."""

    decorators: list[str] = field(default_factory=list)
    """Decorators/annotations, e.g. ['@app.route("/users")']."""

    fields: list[str] = field(default_factory=list)
    """Struct/class fields, e.g. ['Name string', 'age: int']."""

    line: int = 0
    """1-based line number in source file."""

    file: str = ""
    """Relative file path."""


# ---------------------------------------------------------------------------
# Language extractor protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ASTLanguageExtractor(Protocol):
    """Protocol for language-specific tree-sitter extractors.

    Each language implements this to extract symbols, endpoints, and schemas
    from source code using tree-sitter AST nodes.
    """

    language_name: str
    """Language identifier (e.g., 'go', 'python', 'typescript')."""

    file_extensions: list[str]
    """Extensions this extractor handles (e.g., ['.go'], ['.py'])."""

    def extract_symbols(self, content: str, file_path: str) -> list[ASTSymbol]:
        """Extract all code symbols (functions, classes, types, etc.).

        Args:
            content: Source file content as string.
            file_path: Relative file path for location tracking.

        Returns:
            List of ASTSymbol with full signature information.
        """
        ...

    def extract_endpoints(self, content: str, file_path: str) -> list[FactItem]:
        """Extract HTTP endpoint registrations.

        Looks for framework-specific patterns like http.HandleFunc,
        @app.route, router.get, etc.

        Args:
            content: Source file content as string.
            file_path: Relative file path for location tracking.

        Returns:
            List of FactItem with fact_type='endpoint'.
        """
        ...

    def extract_schemas(self, content: str, file_path: str) -> list[ASTSymbol]:
        """Extract database/validation schema definitions.

        Looks for ORM models, Pydantic/Zod schemas, SQL definitions.

        Args:
            content: Source file content as string.
            file_path: Relative file path for location tracking.

        Returns:
            List of ASTSymbol with kind='schema'.
        """
        ...


# ---------------------------------------------------------------------------
# Helpers for tree-sitter node traversal
# ---------------------------------------------------------------------------


def get_parser(language: str):
    """Get a tree-sitter parser for the given language.

    Returns None if tree-sitter-language-pack is not available.
    """
    try:
        import tree_sitter_language_pack as tslp
        return tslp.get_parser(language)
    except (ImportError, Exception) as e:
        logger.debug("Cannot get tree-sitter parser for %s: %s", language, e)
        return None


def parse_source(parser, content: str):
    """Parse source content into a tree-sitter tree.

    Args:
        parser: A tree-sitter Parser instance.
        content: Source code as string.

    Returns:
        The root node of the parsed tree, or None on failure.
    """
    if parser is None:
        return None
    try:
        tree = parser.parse(content.encode("utf-8"))
        return tree.root_node
    except Exception as e:
        logger.debug("tree-sitter parse failed: %s", e)
        return None


def node_text(node) -> str:
    """Extract text from a tree-sitter node, decoded as UTF-8."""
    if node is None:
        return ""
    return node.text.decode("utf-8") if isinstance(node.text, bytes) else str(node.text)


def find_children(node, *types: str):
    """Find direct children of a node matching any of the given types."""
    return [c for c in node.children if c.type in types]


def find_first_child(node, *types: str):
    """Find the first direct child matching any of the given types."""
    for c in node.children:
        if c.type in types:
            return c
    return None
