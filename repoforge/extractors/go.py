"""
Go Extractor

Regex-based extractor for Go files.
Handles import blocks, single imports, aliased/dot imports,
and exported identifiers (uppercase convention).
Ported from ghagga's go.ts.
"""

import re

from .types import ExportInfo, ImportInfo


# ---------------------------------------------------------------------------
# Import Patterns
# ---------------------------------------------------------------------------

# Single import: import "pkg" / import alias "pkg" / import . "pkg"
SINGLE_IMPORT_RE = re.compile(
    r'^import\s+(?:(\w+|\.)\s+)?["\']([^"\']+)["\']', re.MULTILINE
)

# Import block: import ( ... ) — captures the block content
IMPORT_BLOCK_RE = re.compile(r"import\s*\(\s*([\s\S]*?)\)")

# Line inside import block: optional-alias "pkg"
IMPORT_LINE_RE = re.compile(r'(?:(\w+|\.)\s+)?["\']([^"\']+)["\']')

# ---------------------------------------------------------------------------
# Export Patterns (Go: uppercase = exported)
# ---------------------------------------------------------------------------

# func FuncName( — exported functions, including methods (with receiver)
FUNC_RE = re.compile(
    r"^func\s+(?:\([^)]*\)\s+)?([A-Z]\w*)\s*\(", re.MULTILINE
)

# type TypeName struct/interface/...
TYPE_RE = re.compile(
    r"^type\s+([A-Z]\w*)\s+(?:struct|interface)\b", re.MULTILINE
)

# var/const VarName — exported package-level vars/consts
VAR_RE = re.compile(
    r"^(?:var|const)\s+([A-Z]\w*)\s", re.MULTILINE
)

# ---------------------------------------------------------------------------
# Go standard library detection
# ---------------------------------------------------------------------------

# Go stdlib packages don't have a dot in them (no domain)
# e.g., "fmt", "os", "net/http" vs "github.com/user/pkg"
_STDLIB_RE = re.compile(r"^[a-z][a-z0-9]*(?:/[a-z][a-z0-9]*)*$")

# ---------------------------------------------------------------------------
# Test file pattern
# ---------------------------------------------------------------------------

TEST_FILE_RE = re.compile(r"_test\.go$")


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class GoExtractor:
    """Regex-based extractor for Go files."""

    language: str = "go"
    extensions: list[str] = [".go"]

    def extract_imports(self, content: str) -> list[ImportInfo]:
        imports: list[ImportInfo] = []
        seen: set[str] = set()

        def add_import(source: str, alias: str | None = None) -> None:
            if source in seen:
                return
            seen.add(source)
            symbols = [alias] if alias else []
            # Relative = not stdlib and not external (contains a dot like github.com)
            # In Go, "relative" means same module — no dot in path AND not stdlib
            # For simplicity: stdlib has no dots, external has dots
            is_relative = not _is_stdlib(source) and "." not in source
            imports.append(ImportInfo(
                source=source, symbols=symbols, is_relative=is_relative,
            ))

        # Import blocks first
        for block_match in IMPORT_BLOCK_RE.finditer(content):
            block_content = block_match.group(1)
            for line_match in IMPORT_LINE_RE.finditer(block_content):
                alias = line_match.group(1)
                source = line_match.group(2)
                add_import(source, alias)

        # Single imports
        for match in SINGLE_IMPORT_RE.finditer(content):
            alias = match.group(1)
            source = match.group(2)
            add_import(source, alias)

        return imports

    def extract_exports(self, content: str) -> list[ExportInfo]:
        exports: list[ExportInfo] = []
        seen: set[str] = set()

        def add(name: str, kind: str) -> None:
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(name=name, kind=kind))

        # Exported functions (including methods)
        for match in FUNC_RE.finditer(content):
            add(match.group(1), "function")

        # Exported types
        for match in TYPE_RE.finditer(content):
            add(match.group(1), "type")

        # Exported vars/consts
        for match in VAR_RE.finditer(content):
            add(match.group(1), "variable")

        return exports

    def detect_test_file(self, file_path: str) -> bool:
        return bool(TEST_FILE_RE.search(file_path))


def _is_stdlib(source: str) -> bool:
    """Heuristic: Go stdlib packages are lowercase with no dots."""
    return bool(_STDLIB_RE.match(source))
