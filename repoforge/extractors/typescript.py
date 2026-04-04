"""
TypeScript Extractor

Regex-based extractor for TypeScript/TSX files.
Handles ES module imports/exports including type-only imports.
Ported from ghagga's typescript.ts.
"""

import re

from .types import ExportInfo, ImportInfo

# ---------------------------------------------------------------------------
# Import Patterns
# ---------------------------------------------------------------------------

# import { x, y } from 'module' — also handles `import type { x } from 'module'`
NAMED_IMPORT_RE = re.compile(
    r"import\s+(?:type\s+)?{([^}]+)}\s+from\s+['\"]([^'\"]+)['\"]"
)

# import x from 'module' — default import
DEFAULT_IMPORT_RE = re.compile(
    r"import\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"]"
)

# import * as x from 'module' — namespace import
NAMESPACE_IMPORT_RE = re.compile(
    r"import\s+\*\s+as\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"]"
)

# import 'module' — side-effect import
SIDE_EFFECT_IMPORT_RE = re.compile(
    r"import\s+['\"]([^'\"]+)['\"]"
)

# import x, { y, z } from 'module' — mixed default + named
MIXED_IMPORT_RE = re.compile(
    r"import\s+(\w+)\s*,\s*{([^}]+)}\s+from\s+['\"]([^'\"]+)['\"]"
)

# dynamic import: import('module') or await import('module')
DYNAMIC_IMPORT_RE = re.compile(
    r"(?:await\s+)?import\(\s*['\"]([^'\"]+)['\"]\s*\)"
)

# ---------------------------------------------------------------------------
# Export Patterns
# ---------------------------------------------------------------------------

# export function x() / export async function x()
EXPORT_FUNCTION_RE = re.compile(r"export\s+(?:async\s+)?function\s+(\w+)")

# export class x
EXPORT_CLASS_RE = re.compile(r"export\s+class\s+(\w+)")

# export const/let/var x
EXPORT_VARIABLE_RE = re.compile(r"export\s+(?:const|let|var)\s+(\w+)")

# export type x / export interface x
EXPORT_TYPE_RE = re.compile(r"export\s+(?:type|interface)\s+(\w+)")

# export default (named)
EXPORT_DEFAULT_RE = re.compile(
    r"export\s+default\s+(?:function\s+(\w+)|class\s+(\w+)|(\w+))"
)

# export { x, y, z } — re-exports or named exports
EXPORT_NAMED_RE = re.compile(r"export\s+{([^}]+)}")

# export default (anonymous) — export default function() {}, export default class {}
EXPORT_DEFAULT_ANON_RE = re.compile(
    r"export\s+default\s+(?:function|class)\s*[({]"
)

# ---------------------------------------------------------------------------
# Test file pattern
# ---------------------------------------------------------------------------

TEST_FILE_RE = re.compile(r"\.(?:test|spec)\.tsx?$")


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class TypeScriptExtractor:
    """Regex-based extractor for TypeScript and TSX files."""

    language: str = "typescript"
    extensions: list[str] = [".ts", ".tsx"]

    def extract_imports(self, content: str) -> list[ImportInfo]:
        imports: list[ImportInfo] = []
        seen: set[str] = set()

        # Mixed default + named: import x, { y, z } from 'module'
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
                is_relative = source.startswith(".")
                imports.append(ImportInfo(source=source, symbols=symbols, is_relative=is_relative))

        # Named imports: import { x, y } from 'module'
        for match in NAMED_IMPORT_RE.finditer(content):
            symbols_raw = match.group(1)
            source = match.group(2)
            symbols = [
                s.strip().split(" as ")[0].strip()
                for s in symbols_raw.split(",")
                if s.strip()
            ]
            key = f"{source}:named"
            if key not in seen:
                seen.add(key)
                is_relative = source.startswith(".")
                imports.append(ImportInfo(source=source, symbols=symbols, is_relative=is_relative))

        # Default imports: import x from 'module'
        for match in DEFAULT_IMPORT_RE.finditer(content):
            name = match.group(1)
            source = match.group(2)
            key = f"{source}:default"
            if key not in seen:
                seen.add(key)
                is_relative = source.startswith(".")
                imports.append(ImportInfo(source=source, symbols=[name], is_relative=is_relative))

        # Namespace imports: import * as x from 'module'
        for match in NAMESPACE_IMPORT_RE.finditer(content):
            name = match.group(1)
            source = match.group(2)
            key = f"{source}:namespace"
            if key not in seen:
                seen.add(key)
                is_relative = source.startswith(".")
                imports.append(ImportInfo(source=source, symbols=[name], is_relative=is_relative))

        # Side-effect imports: import 'module'
        for match in SIDE_EFFECT_IMPORT_RE.finditer(content):
            source = match.group(1)
            key = f"{source}:side-effect"
            if key not in seen:
                seen.add(key)
                imports.append(ImportInfo(source=source, symbols=[], is_relative=source.startswith(".")))

        # Dynamic imports: import('module')
        for match in DYNAMIC_IMPORT_RE.finditer(content):
            source = match.group(1)
            key = f"{source}:dynamic"
            if key not in seen:
                seen.add(key)
                imports.append(ImportInfo(source=source, symbols=[], is_relative=source.startswith(".")))

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

        # export type/interface
        for match in EXPORT_TYPE_RE.finditer(content):
            add(match.group(1), "type")

        # export { x, y, z }
        for match in EXPORT_NAMED_RE.finditer(content):
            names = [
                s.strip().split(" as ")[0].strip()
                for s in match.group(1).split(",")
                if s.strip()
            ]
            for name in names:
                add(name, "variable")

        return exports

    def detect_test_file(self, file_path: str) -> bool:
        return bool(TEST_FILE_RE.search(file_path))
