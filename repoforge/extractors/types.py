"""
Extractor Types

Shared interfaces for language-specific import/export extractors.
Extractors are pure functions that parse file content using regex
patterns — no native dependencies (no tree-sitter).
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Extracted Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ImportInfo:
    """Represents a single import statement extracted from source code."""

    source: str
    """Module path (e.g., './utils', 'lodash', 'fmt')."""

    symbols: list[str] = field(default_factory=list)
    """Imported symbol names (empty for namespace/wildcard imports)."""

    is_relative: bool = False
    """True for ./utils, ../core, False for 'fmt', 'lodash'."""


@dataclass(frozen=True, slots=True)
class ExportInfo:
    """Represents a single export declaration extracted from source code."""

    name: str
    """Exported symbol name."""

    kind: str = "variable"
    """Kind of export: 'function', 'class', 'variable', 'type', 'default', 'interface'."""


# ---------------------------------------------------------------------------
# Extractor Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Extractor(Protocol):
    """Language-specific extractor interface.

    Implementations parse file content with regex patterns and return
    structured import/export information. No inheritance required —
    any class matching this shape satisfies the protocol.
    """

    language: str
    """Language this extractor handles (e.g., 'typescript', 'python')."""

    extensions: list[str]
    """File extensions this extractor applies to (e.g., ['.ts', '.tsx'])."""

    def extract_imports(self, content: str) -> list[ImportInfo]:
        """Extract import statements from file content."""
        ...

    def extract_exports(self, content: str) -> list[ExportInfo]:
        """Extract export declarations from file content."""
        ...

    def detect_test_file(self, file_path: str) -> bool:
        """Detect whether a file path is a test file for this language."""
        ...
