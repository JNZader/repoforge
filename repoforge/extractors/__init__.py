"""
Extractor Registry

Maps file extensions to language-specific regex-based extractors.
Used by the graph builder to select the right parser for each file.
"""

from .registry import ExtractorRegistry
from .types import ExportInfo, Extractor, ImportInfo

# ---------------------------------------------------------------------------
# Module-level registry instance
# ---------------------------------------------------------------------------

_registry = ExtractorRegistry()


def get_extractor(file_path: str) -> Extractor | None:
    """Get the extractor for a given file path based on its extension."""
    return _registry.get_for_file(file_path)


def get_registry() -> ExtractorRegistry:
    """Get the module-level registry instance."""
    return _registry


def supported_extensions() -> list[str]:
    """List all file extensions with registered extractors."""
    return _registry.supported_extensions()


# ---------------------------------------------------------------------------
# Re-exports
# ---------------------------------------------------------------------------

__all__ = [
    "ExportInfo",
    "Extractor",
    "ExtractorRegistry",
    "ImportInfo",
    "get_extractor",
    "get_registry",
    "supported_extensions",
]
