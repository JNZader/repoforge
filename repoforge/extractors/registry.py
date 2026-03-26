"""
Extractor Registry

Maps file extensions to their corresponding language extractors.
Provides lookup by file path and tracks all supported extensions.
"""

from pathlib import PurePosixPath

from .types import Extractor


class ExtractorRegistry:
    """Registry that maps file extensions to language extractors.

    Each extractor declares which extensions it handles. The registry
    builds an extension -> extractor lookup table for O(1) file dispatch.
    """

    def __init__(self) -> None:
        self._extractors: dict[str, Extractor] = {}

    def register(self, extractor: Extractor) -> None:
        """Register an extractor for all its declared extensions.

        If an extension is already registered, the new extractor
        overwrites the previous one (last-write-wins).
        """
        for ext in extractor.extensions:
            normalized = ext if ext.startswith(".") else f".{ext}"
            self._extractors[normalized] = extractor

    def get_for_file(self, file_path: str) -> Extractor | None:
        """Return the extractor for a file based on its extension.

        Returns None if no extractor is registered for the file's extension.
        """
        suffix = PurePosixPath(file_path).suffix
        return self._extractors.get(suffix)

    def supported_extensions(self) -> list[str]:
        """Return a sorted list of all registered file extensions."""
        return sorted(self._extractors.keys())

    def __len__(self) -> int:
        return len(self._extractors)

    def __contains__(self, extension: str) -> bool:
        normalized = extension if extension.startswith(".") else f".{extension}"
        return normalized in self._extractors
