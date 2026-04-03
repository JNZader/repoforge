"""
AST Extractor Registry — maps file extensions to tree-sitter extractors.

Provides tiered extraction: tree-sitter (if available) -> regex fallback.
Integrates with the existing ExtractorRegistry from repoforge.extractors.
"""

from __future__ import annotations

import logging
from pathlib import PurePosixPath

from .ast_extractor import ASTLanguageExtractor, ASTSymbol
from ..facts import FactItem

logger = logging.getLogger(__name__)


class ASTExtractorRegistry:
    """Registry for tree-sitter AST language extractors.

    Maps file extensions to ASTLanguageExtractor instances.
    Provides a single entry point for symbol, endpoint, and schema extraction.
    """

    def __init__(self) -> None:
        self._extractors: dict[str, ASTLanguageExtractor] = {}

    def register(self, extractor: ASTLanguageExtractor) -> None:
        """Register an extractor for all its declared file extensions."""
        for ext in extractor.file_extensions:
            normalized = ext if ext.startswith(".") else f".{ext}"
            self._extractors[normalized] = extractor

    def get_for_file(self, file_path: str) -> ASTLanguageExtractor | None:
        """Return the AST extractor for a file based on its extension."""
        suffix = PurePosixPath(file_path).suffix
        return self._extractors.get(suffix)

    def extract_symbols(self, content: str, file_path: str) -> list[ASTSymbol]:
        """Extract symbols using the appropriate language extractor.

        Returns empty list if no extractor is registered for the file type.
        """
        extractor = self.get_for_file(file_path)
        if not extractor:
            return []
        try:
            return extractor.extract_symbols(content, file_path)
        except (SyntaxError, ValueError, TypeError, AttributeError):
            # tree-sitter parse errors or malformed AST node access
            logger.debug("AST symbol extraction failed for %s", file_path, exc_info=True)
            return []

    def extract_endpoints(self, content: str, file_path: str) -> list[FactItem]:
        """Extract HTTP endpoints using the appropriate language extractor."""
        extractor = self.get_for_file(file_path)
        if not extractor:
            return []
        try:
            return extractor.extract_endpoints(content, file_path)
        except (SyntaxError, ValueError, TypeError, AttributeError):
            # tree-sitter parse errors or malformed AST node access
            logger.debug("AST endpoint extraction failed for %s", file_path, exc_info=True)
            return []

    def extract_schemas(self, content: str, file_path: str) -> list[ASTSymbol]:
        """Extract schema definitions using the appropriate language extractor."""
        extractor = self.get_for_file(file_path)
        if not extractor:
            return []
        try:
            return extractor.extract_schemas(content, file_path)
        except (SyntaxError, ValueError, TypeError, AttributeError):
            # tree-sitter parse errors or malformed AST node access
            logger.debug("AST schema extraction failed for %s", file_path, exc_info=True)
            return []

    def supported_extensions(self) -> list[str]:
        """Return sorted list of all registered extensions."""
        return sorted(self._extractors.keys())

    def __len__(self) -> int:
        return len(self._extractors)


# ---------------------------------------------------------------------------
# Module-level singleton — populated only when tree-sitter is available
# ---------------------------------------------------------------------------

_ast_registry: ASTExtractorRegistry | None = None


def get_ast_registry() -> ASTExtractorRegistry | None:
    """Get the AST extractor registry, creating it lazily.

    Returns None if tree-sitter is not available (intelligence extras not installed).
    Uses lazy initialization to avoid import-time failures.
    """
    global _ast_registry
    if _ast_registry is not None:
        return _ast_registry

    from . import INTELLIGENCE_AVAILABLE
    if not INTELLIGENCE_AVAILABLE:
        return None

    try:
        _ast_registry = ASTExtractorRegistry()

        from .lang_go import GoASTExtractor
        from .lang_python import PythonASTExtractor
        from .lang_typescript import TypeScriptASTExtractor
        from .lang_javascript import JavaScriptASTExtractor
        from .lang_java import JavaASTExtractor
        from .lang_rust import RustASTExtractor

        _ast_registry.register(GoASTExtractor())
        _ast_registry.register(PythonASTExtractor())
        _ast_registry.register(TypeScriptASTExtractor())
        _ast_registry.register(JavaScriptASTExtractor())
        _ast_registry.register(JavaASTExtractor())
        _ast_registry.register(RustASTExtractor())

        logger.debug(
            "AST extractor registry initialized with %d extensions: %s",
            len(_ast_registry),
            _ast_registry.supported_extensions(),
        )
        return _ast_registry

    except (ImportError, OSError, RuntimeError):
        # ImportError: tree-sitter language bindings not installed
        # OSError: shared library loading failure
        # RuntimeError: tree-sitter initialization errors
        logger.debug("Failed to initialize AST extractor registry", exc_info=True)
        _ast_registry = None
        return None


def ast_extract_symbols(content: str, file_path: str) -> list[ASTSymbol]:
    """Convenience function: extract symbols from a file using tree-sitter.

    Falls back to empty list if tree-sitter is not available.
    """
    registry = get_ast_registry()
    if registry is None:
        return []
    return registry.extract_symbols(content, file_path)


def ast_extract_endpoints(content: str, file_path: str) -> list[FactItem]:
    """Convenience function: extract endpoints from a file using tree-sitter."""
    registry = get_ast_registry()
    if registry is None:
        return []
    return registry.extract_endpoints(content, file_path)


def ast_extract_schemas(content: str, file_path: str) -> list[ASTSymbol]:
    """Convenience function: extract schemas from a file using tree-sitter."""
    registry = get_ast_registry()
    if registry is None:
        return []
    return registry.extract_schemas(content, file_path)
