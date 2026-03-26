"""
Java Extractor

Regex-based extractor for Java files.
Handles import statements and public class/interface/enum/record declarations.
Ported from ghagga's java.ts.
"""

import re

from .types import ExportInfo, ImportInfo


# ---------------------------------------------------------------------------
# Import Patterns
# ---------------------------------------------------------------------------

# import x.y.z; / import static x.y.z;
IMPORT_RE = re.compile(
    r"^import\s+(?:static\s+)?([\w.]+(?:\.\*)?)\s*;", re.MULTILINE
)

# ---------------------------------------------------------------------------
# Export Patterns
# ---------------------------------------------------------------------------

# public class ClassName / public abstract class ClassName
PUBLIC_CLASS_RE = re.compile(r"public\s+(?:abstract\s+)?class\s+(\w+)")

# public interface InterfaceName
PUBLIC_INTERFACE_RE = re.compile(r"public\s+interface\s+(\w+)")

# public enum EnumName
PUBLIC_ENUM_RE = re.compile(r"public\s+enum\s+(\w+)")

# public record RecordName
PUBLIC_RECORD_RE = re.compile(r"public\s+record\s+(\w+)")

# public [static] [final] ReturnType methodName( — public methods
PUBLIC_METHOD_RE = re.compile(
    r"public\s+(?:static\s+)?(?:final\s+)?[\w<>\[\],\s]+\s+(\w+)\s*\("
)

# Java boilerplate methods to exclude
_JAVA_NOISE = frozenset({"main", "toString", "hashCode", "equals", "clone"})

# ---------------------------------------------------------------------------
# Test file pattern
# ---------------------------------------------------------------------------

TEST_FILE_RE = re.compile(r"(?:Test|Tests|IT)\.java$")


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class JavaExtractor:
    """Regex-based extractor for Java files."""

    language: str = "java"
    extensions: list[str] = [".java"]

    def extract_imports(self, content: str) -> list[ImportInfo]:
        imports: list[ImportInfo] = []
        seen: set[str] = set()

        for match in IMPORT_RE.finditer(content):
            full_path = match.group(1)
            if full_path in seen:
                continue
            seen.add(full_path)

            # Extract the class/symbol name (last segment)
            parts = full_path.split(".")
            last_part = parts[-1]
            symbols = [] if last_part == "*" else [last_part]

            imports.append(ImportInfo(
                source=full_path, symbols=symbols, is_relative=False,
            ))

        return imports

    def extract_exports(self, content: str) -> list[ExportInfo]:
        exports: list[ExportInfo] = []
        seen: set[str] = set()

        def add(name: str, kind: str) -> None:
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(name=name, kind=kind))

        # Public classes
        for match in PUBLIC_CLASS_RE.finditer(content):
            add(match.group(1), "class")

        # Public interfaces
        for match in PUBLIC_INTERFACE_RE.finditer(content):
            add(match.group(1), "type")

        # Public enums
        for match in PUBLIC_ENUM_RE.finditer(content):
            add(match.group(1), "type")

        # Public records
        for match in PUBLIC_RECORD_RE.finditer(content):
            add(match.group(1), "type")

        # Public methods (exclude boilerplate)
        for match in PUBLIC_METHOD_RE.finditer(content):
            name = match.group(1)
            if name not in _JAVA_NOISE and name not in seen:
                add(name, "function")

        return exports

    def detect_test_file(self, file_path: str) -> bool:
        return bool(TEST_FILE_RE.search(file_path))
