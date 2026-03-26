"""
Python Extractor

Regex-based extractor for Python files.
Handles absolute imports, relative imports, and function/class definitions.
Ported from ghagga's python.ts.
"""

import re

from .types import ExportInfo, ImportInfo


# ---------------------------------------------------------------------------
# Import Patterns
# ---------------------------------------------------------------------------

# from x import y, z  /  from . import y  /  from ...pkg import z
FROM_IMPORT_RE = re.compile(
    r"^from\s+(\.{0,3}\w[\w.]*|\.{1,3})\s+import\s+(.+)$", re.MULTILINE
)

# import x  /  import x, y  /  import x as y
IMPORT_RE = re.compile(
    r"^import\s+([\w.]+(?:\s+as\s+\w+)?(?:\s*,\s*[\w.]+(?:\s+as\s+\w+)?)*)$",
    re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Export Patterns
# ---------------------------------------------------------------------------

# def function_name(
FUNCTION_DEF_RE = re.compile(r"^def\s+(\w+)\s*\(", re.MULTILINE)

# class ClassName
CLASS_DEF_RE = re.compile(r"^class\s+(\w+)", re.MULTILINE)

# Top-level UPPER_CASE variable assignment
TOP_LEVEL_VAR_RE = re.compile(r"^([A-Z_][A-Z0-9_]*)\s*=", re.MULTILINE)

# __all__ = ['x', 'y', 'z']
ALL_LIST_RE = re.compile(r"__all__\s*=\s*\[([^\]]+)\]")

# ---------------------------------------------------------------------------
# Test file pattern
# ---------------------------------------------------------------------------

TEST_FILE_RE = re.compile(r"(?:^|/)test_\w+\.py$|(?:^|/)\w+_test\.py$")


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class PythonExtractor:
    """Regex-based extractor for Python files."""

    language: str = "python"
    extensions: list[str] = [".py"]

    def extract_imports(self, content: str) -> list[ImportInfo]:
        imports: list[ImportInfo] = []
        seen: set[str] = set()

        # from x import y, z
        for match in FROM_IMPORT_RE.finditer(content):
            source = match.group(1)
            import_part = match.group(2).strip()

            # Handle `from x import (y, z)` — multi-line with parens
            cleaned = import_part.replace("(", "").replace(")", "")
            symbols = [
                s.strip().split(" as ")[0].strip()
                for s in cleaned.split(",")
                if s.strip() and s.strip() != "*"
            ]

            is_relative = source.startswith(".")
            key = f"{source}:from"
            if key not in seen:
                seen.add(key)
                imports.append(ImportInfo(
                    source=source, symbols=symbols, is_relative=is_relative,
                ))

        # import x / import x, y
        for match in IMPORT_RE.finditer(content):
            modules_part = match.group(1)
            modules = [
                s.strip().split(" as ")[0].strip()
                for s in modules_part.split(",")
                if s.strip()
            ]
            for mod in modules:
                key = f"{mod}:import"
                if key not in seen:
                    seen.add(key)
                    imports.append(ImportInfo(
                        source=mod, symbols=[], is_relative=False,
                    ))

        return imports

    def extract_exports(self, content: str) -> list[ExportInfo]:
        exports: list[ExportInfo] = []
        seen: set[str] = set()

        def add(name: str, kind: str) -> None:
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(name=name, kind=kind))

        # Check for __all__ — if present, only export those names
        all_match = ALL_LIST_RE.search(content)
        if all_match:
            names = [
                s.strip().strip("'\"")
                for s in all_match.group(1).split(",")
                if s.strip()
            ]
            for name in names:
                add(name, "variable")
            return exports

        # Public functions (not starting with _)
        for match in FUNCTION_DEF_RE.finditer(content):
            name = match.group(1)
            if not name.startswith("_"):
                add(name, "function")

        # Public classes (not starting with _)
        for match in CLASS_DEF_RE.finditer(content):
            name = match.group(1)
            if not name.startswith("_"):
                add(name, "class")

        # Top-level constants
        for match in TOP_LEVEL_VAR_RE.finditer(content):
            add(match.group(1), "variable")

        return exports

    def detect_test_file(self, file_path: str) -> bool:
        return bool(TEST_FILE_RE.search(file_path))
