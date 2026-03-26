"""
JavaScript Extractor

Regex-based extractor for JavaScript/JSX/MJS/CJS files.
Handles ES module imports/exports AND CommonJS require/module.exports.
Ported from ghagga's javascript.ts.
"""

import re

from .types import ExportInfo, ImportInfo


# ---------------------------------------------------------------------------
# ES Module Import Patterns
# ---------------------------------------------------------------------------

# import { x, y } from 'module'
NAMED_IMPORT_RE = re.compile(
    r"import\s+{([^}]+)}\s+from\s+['\"]([^'\"]+)['\"]"
)

# import x from 'module'
DEFAULT_IMPORT_RE = re.compile(
    r"import\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"]"
)

# import * as x from 'module'
NAMESPACE_IMPORT_RE = re.compile(
    r"import\s+\*\s+as\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"]"
)

# import 'module'
SIDE_EFFECT_IMPORT_RE = re.compile(
    r"import\s+['\"]([^'\"]+)['\"]"
)

# import x, { y, z } from 'module'
MIXED_IMPORT_RE = re.compile(
    r"import\s+(\w+)\s*,\s*{([^}]+)}\s+from\s+['\"]([^'\"]+)['\"]"
)

# ---------------------------------------------------------------------------
# CommonJS Import Patterns
# ---------------------------------------------------------------------------

# const x = require('module') / const { x, y } = require('module')
REQUIRE_RE = re.compile(
    r"(?:const|let|var)\s+(?:(\w+)|{([^}]+)})\s*=\s*require\(\s*['\"]([^'\"]+)['\"]\s*\)"
)

# require('module') — bare require (side-effect)
BARE_REQUIRE_RE = re.compile(
    r"^require\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE
)

# ---------------------------------------------------------------------------
# ES Module Export Patterns
# ---------------------------------------------------------------------------

# export function x() / export async function x()
EXPORT_FUNCTION_RE = re.compile(r"export\s+(?:async\s+)?function\s+(\w+)")

# export class x
EXPORT_CLASS_RE = re.compile(r"export\s+class\s+(\w+)")

# export const/let/var x
EXPORT_VARIABLE_RE = re.compile(r"export\s+(?:const|let|var)\s+(\w+)")

# export default
EXPORT_DEFAULT_RE = re.compile(
    r"export\s+default\s+(?:function\s+(\w+)|class\s+(\w+)|(\w+))"
)

# export { x, y }
EXPORT_NAMED_RE = re.compile(r"export\s+{([^}]+)}")

# export default anonymous
EXPORT_DEFAULT_ANON_RE = re.compile(
    r"export\s+default\s+(?:function|class)\s*[({]"
)

# ---------------------------------------------------------------------------
# CommonJS Export Patterns
# ---------------------------------------------------------------------------

# module.exports = x / module.exports = { x, y }
MODULE_EXPORTS_RE = re.compile(
    r"module\.exports\s*=\s*(?:{([^}]+)}|(\w+))"
)

# exports.x = ...
EXPORTS_PROP_RE = re.compile(r"exports\.(\w+)\s*=")

# ---------------------------------------------------------------------------
# Test file pattern
# ---------------------------------------------------------------------------

TEST_FILE_RE = re.compile(r"\.(?:test|spec)\.(?:js|jsx|mjs|cjs)$")


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class JavaScriptExtractor:
    """Regex-based extractor for JavaScript, JSX, MJS, and CJS files."""

    language: str = "javascript"
    extensions: list[str] = [".js", ".jsx", ".mjs", ".cjs"]

    def extract_imports(self, content: str) -> list[ImportInfo]:
        imports: list[ImportInfo] = []
        seen: set[str] = set()

        # Mixed default + named
        for match in MIXED_IMPORT_RE.finditer(content):
            default_name = match.group(1)
            named_part = match.group(2)
            source = match.group(3)
            symbols = [default_name] + [
                s.strip().split(" as ")[0].strip()
                for s in named_part.split(",")
                if s.strip()
            ]
            key = f"{source}:{','.join(sorted(symbols))}"
            if key not in seen:
                seen.add(key)
                imports.append(ImportInfo(
                    source=source, symbols=symbols,
                    is_relative=source.startswith("."),
                ))

        # Named imports
        for match in NAMED_IMPORT_RE.finditer(content):
            symbols = [
                s.strip().split(" as ")[0].strip()
                for s in match.group(1).split(",")
                if s.strip()
            ]
            source = match.group(2)
            key = f"{source}:named"
            if key not in seen:
                seen.add(key)
                imports.append(ImportInfo(
                    source=source, symbols=symbols,
                    is_relative=source.startswith("."),
                ))

        # Default imports
        for match in DEFAULT_IMPORT_RE.finditer(content):
            name = match.group(1)
            source = match.group(2)
            key = f"{source}:default"
            if key not in seen:
                seen.add(key)
                imports.append(ImportInfo(
                    source=source, symbols=[name],
                    is_relative=source.startswith("."),
                ))

        # Namespace imports
        for match in NAMESPACE_IMPORT_RE.finditer(content):
            name = match.group(1)
            source = match.group(2)
            key = f"{source}:namespace"
            if key not in seen:
                seen.add(key)
                imports.append(ImportInfo(
                    source=source, symbols=[name],
                    is_relative=source.startswith("."),
                ))

        # Side-effect imports
        for match in SIDE_EFFECT_IMPORT_RE.finditer(content):
            source = match.group(1)
            key = f"{source}:side-effect"
            if key not in seen:
                seen.add(key)
                imports.append(ImportInfo(
                    source=source, symbols=[],
                    is_relative=source.startswith("."),
                ))

        # CommonJS require
        for match in REQUIRE_RE.finditer(content):
            default_name = match.group(1)
            named_part = match.group(2)
            source = match.group(3)
            if default_name:
                symbols = [default_name]
            elif named_part:
                symbols = [
                    s.strip().split(":")[0].strip()
                    for s in named_part.split(",")
                    if s.strip()
                ]
            else:
                symbols = []
            key = f"{source}:require"
            if key not in seen:
                seen.add(key)
                imports.append(ImportInfo(
                    source=source, symbols=symbols,
                    is_relative=source.startswith("."),
                ))

        # Bare require
        for match in BARE_REQUIRE_RE.finditer(content):
            source = match.group(1)
            key = f"{source}:bare-require"
            if key not in seen:
                seen.add(key)
                imports.append(ImportInfo(
                    source=source, symbols=[],
                    is_relative=source.startswith("."),
                ))

        return imports

    def extract_exports(self, content: str) -> list[ExportInfo]:
        exports: list[ExportInfo] = []
        seen: set[str] = set()

        def add(name: str, kind: str) -> None:
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(name=name, kind=kind))

        # export default (named)
        for match in EXPORT_DEFAULT_RE.finditer(content):
            name = match.group(1) or match.group(2) or match.group(3)
            if name:
                add(name, "default")

        # export default (anonymous)
        for _match in EXPORT_DEFAULT_ANON_RE.finditer(content):
            if "default" not in seen:
                add("default", "default")

        # export function
        for match in EXPORT_FUNCTION_RE.finditer(content):
            add(match.group(1), "function")

        # export class
        for match in EXPORT_CLASS_RE.finditer(content):
            add(match.group(1), "class")

        # export const/let/var
        for match in EXPORT_VARIABLE_RE.finditer(content):
            add(match.group(1), "variable")

        # export { x, y }
        for match in EXPORT_NAMED_RE.finditer(content):
            names = [
                s.strip().split(" as ")[0].strip()
                for s in match.group(1).split(",")
                if s.strip()
            ]
            for name in names:
                add(name, "variable")

        # module.exports = { x, y } or module.exports = x
        for match in MODULE_EXPORTS_RE.finditer(content):
            object_part = match.group(1)
            single_name = match.group(2)
            if object_part:
                names = [
                    s.strip().split(":")[0].strip()
                    for s in object_part.split(",")
                    if s.strip()
                ]
                for name in names:
                    add(name, "variable")
            elif single_name:
                add(single_name, "default")

        # exports.x = ...
        for match in EXPORTS_PROP_RE.finditer(content):
            add(match.group(1), "variable")

        return exports

    def detect_test_file(self, file_path: str) -> bool:
        return bool(TEST_FILE_RE.search(file_path))
