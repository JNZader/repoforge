"""
tests/test_extractors/test_typescript.py — Tests for TypeScriptExtractor.

Tests cover:
- Named imports (including type imports)
- Default imports
- Namespace imports
- Side-effect imports
- Mixed default + named imports
- Dynamic imports
- Export functions, classes, variables, types/interfaces
- Export default (named and anonymous)
- Re-exports (export { x, y })
- Test file detection
"""

import pytest

from repoforge.extractors.typescript import TypeScriptExtractor


@pytest.fixture
def extractor() -> TypeScriptExtractor:
    return TypeScriptExtractor()


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------


class TestExtractImports:
    """Tests for TypeScriptExtractor.extract_imports()."""

    def test_named_import(self, extractor: TypeScriptExtractor) -> None:
        content = "import { foo, bar } from './utils';"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "./utils"
        assert result[0].symbols == ["foo", "bar"]
        assert result[0].is_relative is True

    def test_type_import(self, extractor: TypeScriptExtractor) -> None:
        content = "import type { User } from './models';"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "./models"
        assert result[0].symbols == ["User"]

    def test_default_import(self, extractor: TypeScriptExtractor) -> None:
        content = "import React from 'react';"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "react"
        assert result[0].symbols == ["React"]
        assert result[0].is_relative is False

    def test_namespace_import(self, extractor: TypeScriptExtractor) -> None:
        content = "import * as path from 'path';"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "path"
        assert result[0].symbols == ["path"]

    def test_side_effect_import(self, extractor: TypeScriptExtractor) -> None:
        content = "import './polyfills';"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "./polyfills"
        assert result[0].symbols == []
        assert result[0].is_relative is True

    def test_mixed_import(self, extractor: TypeScriptExtractor) -> None:
        content = "import React, { useState, useEffect } from 'react';"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "react"
        assert "React" in result[0].symbols
        assert "useState" in result[0].symbols
        assert "useEffect" in result[0].symbols

    def test_dynamic_import(self, extractor: TypeScriptExtractor) -> None:
        content = "const mod = await import('./lazy-module');"
        result = extractor.extract_imports(content)
        assert any(i.source == "./lazy-module" for i in result)

    def test_aliased_named_import(self, extractor: TypeScriptExtractor) -> None:
        content = "import { foo as bar } from './utils';"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].symbols == ["foo"]

    def test_multiple_imports(self, extractor: TypeScriptExtractor) -> None:
        content = """
import { a } from './mod-a';
import { b } from './mod-b';
"""
        result = extractor.extract_imports(content)
        assert len(result) == 2
        sources = {i.source for i in result}
        assert sources == {"./mod-a", "./mod-b"}

    def test_relative_detection(self, extractor: TypeScriptExtractor) -> None:
        content = """
import { a } from './local';
import { b } from '../parent';
import { c } from 'lodash';
"""
        result = extractor.extract_imports(content)
        rel = {i.source: i.is_relative for i in result}
        assert rel["./local"] is True
        assert rel["../parent"] is True
        assert rel["lodash"] is False

    def test_no_duplicates(self, extractor: TypeScriptExtractor) -> None:
        content = """
import { a } from './utils';
import { b } from './utils';
"""
        result = extractor.extract_imports(content)
        # Both match as named, keyed by source:named — deduped
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


class TestExtractExports:
    """Tests for TypeScriptExtractor.extract_exports()."""

    def test_export_function(self, extractor: TypeScriptExtractor) -> None:
        content = "export function handleClick() {}"
        result = extractor.extract_exports(content)
        assert len(result) == 1
        assert result[0].name == "handleClick"
        assert result[0].kind == "function"

    def test_export_async_function(self, extractor: TypeScriptExtractor) -> None:
        content = "export async function fetchData() {}"
        result = extractor.extract_exports(content)
        assert len(result) == 1
        assert result[0].name == "fetchData"
        assert result[0].kind == "function"

    def test_export_class(self, extractor: TypeScriptExtractor) -> None:
        content = "export class UserService {}"
        result = extractor.extract_exports(content)
        assert len(result) == 1
        assert result[0].name == "UserService"
        assert result[0].kind == "class"

    def test_export_const(self, extractor: TypeScriptExtractor) -> None:
        content = "export const MAX_RETRIES = 3;"
        result = extractor.extract_exports(content)
        assert len(result) == 1
        assert result[0].name == "MAX_RETRIES"
        assert result[0].kind == "variable"

    def test_export_type(self, extractor: TypeScriptExtractor) -> None:
        content = "export type UserId = string;"
        result = extractor.extract_exports(content)
        assert len(result) == 1
        assert result[0].name == "UserId"
        assert result[0].kind == "type"

    def test_export_interface(self, extractor: TypeScriptExtractor) -> None:
        content = "export interface Config {}"
        result = extractor.extract_exports(content)
        assert len(result) == 1
        assert result[0].name == "Config"
        assert result[0].kind == "type"

    def test_export_default_function(self, extractor: TypeScriptExtractor) -> None:
        content = "export default function main() {}"
        result = extractor.extract_exports(content)
        assert any(e.name == "main" and e.kind == "default" for e in result)

    def test_export_default_class(self, extractor: TypeScriptExtractor) -> None:
        content = "export default class App {}"
        result = extractor.extract_exports(content)
        assert any(e.name == "App" and e.kind == "default" for e in result)

    def test_export_default_anonymous_function(self, extractor: TypeScriptExtractor) -> None:
        content = "export default function() {}"
        result = extractor.extract_exports(content)
        assert any(e.name == "default" and e.kind == "default" for e in result)

    def test_export_default_identifier(self, extractor: TypeScriptExtractor) -> None:
        content = "export default router;"
        result = extractor.extract_exports(content)
        assert any(e.name == "router" and e.kind == "default" for e in result)

    def test_re_export(self, extractor: TypeScriptExtractor) -> None:
        content = "export { foo, bar };"
        result = extractor.extract_exports(content)
        names = {e.name for e in result}
        assert "foo" in names
        assert "bar" in names

    def test_re_export_with_alias(self, extractor: TypeScriptExtractor) -> None:
        content = "export { internal as public };"
        result = extractor.extract_exports(content)
        assert any(e.name == "internal" for e in result)

    def test_multiple_exports(self, extractor: TypeScriptExtractor) -> None:
        content = """
export function foo() {}
export class Bar {}
export const BAZ = 1;
export type Id = string;
"""
        result = extractor.extract_exports(content)
        assert len(result) == 4


# ---------------------------------------------------------------------------
# Test file detection
# ---------------------------------------------------------------------------


class TestDetectTestFile:
    """Tests for TypeScriptExtractor.detect_test_file()."""

    @pytest.mark.parametrize(
        "path",
        [
            "src/utils.test.ts",
            "src/utils.spec.ts",
            "src/App.test.tsx",
            "src/App.spec.tsx",
        ],
    )
    def test_is_test_file(self, extractor: TypeScriptExtractor, path: str) -> None:
        assert extractor.detect_test_file(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "src/utils.ts",
            "src/App.tsx",
            "src/test-helpers.ts",
            "src/__tests__/setup.ts",
        ],
    )
    def test_not_test_file(self, extractor: TypeScriptExtractor, path: str) -> None:
        assert extractor.detect_test_file(path) is False
