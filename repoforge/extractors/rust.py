"""
Rust Extractor

Regex-based extractor for Rust files.
Handles use statements, mod declarations, grouped imports, and pub exports.
Ported from ghagga's rust.ts.
"""

import re

from .types import ExportInfo, ImportInfo

# ---------------------------------------------------------------------------
# Import Patterns
# ---------------------------------------------------------------------------

# use crate::module::item; / use std::collections::HashMap;
# Also handles grouped: use std::{io, fs};  and glob: use std::*;
USE_RE = re.compile(
    r"^use\s+([\w:]+(?:::\{[^}]+\})?(?:::\*)?)\s*;", re.MULTILINE
)

# mod module_name; — external module declaration (links to another file)
MOD_RE = re.compile(r"^(?:pub\s+)?mod\s+(\w+)\s*;", re.MULTILINE)

# ---------------------------------------------------------------------------
# Export Patterns
# ---------------------------------------------------------------------------

# pub fn function_name / pub(crate) fn / pub async fn
PUB_FN_RE = re.compile(
    r"^pub(?:\(\w+\))?\s+(?:async\s+)?fn\s+(\w+)", re.MULTILINE
)

# pub struct StructName
PUB_STRUCT_RE = re.compile(
    r"^pub(?:\(\w+\))?\s+struct\s+(\w+)", re.MULTILINE
)

# pub enum EnumName
PUB_ENUM_RE = re.compile(
    r"^pub(?:\(\w+\))?\s+enum\s+(\w+)", re.MULTILINE
)

# pub trait TraitName
PUB_TRAIT_RE = re.compile(
    r"^pub(?:\(\w+\))?\s+trait\s+(\w+)", re.MULTILINE
)

# pub type TypeName
PUB_TYPE_RE = re.compile(
    r"^pub(?:\(\w+\))?\s+type\s+(\w+)", re.MULTILINE
)

# pub const/static CONST_NAME
PUB_CONST_RE = re.compile(
    r"^pub(?:\(\w+\))?\s+(?:const|static)\s+(\w+)", re.MULTILINE
)

# pub mod module_name — inline public module
PUB_MOD_RE = re.compile(r"^pub\s+mod\s+(\w+)", re.MULTILINE)

# ---------------------------------------------------------------------------
# Test file pattern
# ---------------------------------------------------------------------------

TEST_FILE_RE = re.compile(r"_test\.rs$")
CFG_TEST_RE = re.compile(r"#\[cfg\(test\)\]")


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class RustExtractor:
    """Regex-based extractor for Rust files."""

    language: str = "rust"
    extensions: list[str] = [".rs"]

    def extract_imports(self, content: str) -> list[ImportInfo]:
        imports: list[ImportInfo] = []
        seen: set[str] = set()

        # use statements
        for match in USE_RE.finditer(content):
            full_path = match.group(1)

            # Handle grouped imports: use std::collections::{HashMap, BTreeMap}
            brace_match = re.match(r"^(.+)::\{([^}]+)\}$", full_path)
            if brace_match:
                prefix = brace_match.group(1)
                symbols = [
                    s.strip().split(" as ")[0].strip()
                    for s in brace_match.group(2).split(",")
                    if s.strip()
                ]
                key = f"{prefix}:use"
                if key not in seen:
                    seen.add(key)
                    imports.append(ImportInfo(
                        source=prefix, symbols=symbols,
                        is_relative=prefix.startswith("crate") or prefix.startswith("super"),
                    ))
            else:
                # Single import: use crate::module::Item or use std::*
                parts = full_path.split("::")
                last_part = parts[-1]
                symbols = [] if last_part == "*" else [last_part]
                source = "::".join(parts[:-1]) if len(parts) > 1 else full_path
                key = f"{full_path}:use"
                if key not in seen:
                    seen.add(key)
                    imports.append(ImportInfo(
                        source=source, symbols=symbols,
                        is_relative=full_path.startswith("crate") or full_path.startswith("super"),
                    ))

        # mod declarations (external modules)
        for match in MOD_RE.finditer(content):
            mod_name = match.group(1)
            key = f"mod:{mod_name}"
            if key not in seen:
                seen.add(key)
                imports.append(ImportInfo(
                    source=mod_name, symbols=[], is_relative=True,
                ))

        return imports

    def extract_exports(self, content: str) -> list[ExportInfo]:
        exports: list[ExportInfo] = []
        seen: set[str] = set()

        def add(name: str, kind: str) -> None:
            if name not in seen:
                seen.add(name)
                exports.append(ExportInfo(name=name, kind=kind))

        # pub fn
        for match in PUB_FN_RE.finditer(content):
            add(match.group(1), "function")

        # pub struct
        for match in PUB_STRUCT_RE.finditer(content):
            add(match.group(1), "type")

        # pub enum
        for match in PUB_ENUM_RE.finditer(content):
            add(match.group(1), "type")

        # pub trait
        for match in PUB_TRAIT_RE.finditer(content):
            add(match.group(1), "type")

        # pub type
        for match in PUB_TYPE_RE.finditer(content):
            add(match.group(1), "type")

        # pub const/static
        for match in PUB_CONST_RE.finditer(content):
            add(match.group(1), "variable")

        # pub mod
        for match in PUB_MOD_RE.finditer(content):
            add(match.group(1), "variable")

        return exports

    def detect_test_file(self, file_path: str, content: str | None = None) -> bool:
        if TEST_FILE_RE.search(file_path):
            return True
        if content and CFG_TEST_RE.search(content):
            return True
        return False
