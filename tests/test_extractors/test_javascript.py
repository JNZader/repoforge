"""
tests/test_extractors/test_javascript.py — Tests for JavaScriptExtractor.

Tests cover:
- ES module imports (named, default, namespace, side-effect, mixed)
- CommonJS require (destructured, default, bare)
- ES module exports (function, class, variable, default, re-export)
- CommonJS exports (module.exports, exports.prop)
- Test file detection
"""

import pytest

from repoforge.extractors.javascript import JavaScriptExtractor


@pytest.fixture
def extractor() -> JavaScriptExtractor:
    return JavaScriptExtractor()


# ---------------------------------------------------------------------------
# ES Module Imports
# ---------------------------------------------------------------------------


class TestESImports:
    """Tests for ES module import extraction."""

    def test_named_import(self, extractor: JavaScriptExtractor) -> None:
        content = "import { foo, bar } from './utils';"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "./utils"
        assert result[0].symbols == ["foo", "bar"]

    def test_default_import(self, extractor: JavaScriptExtractor) -> None:
        content = "import React from 'react';"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "react"
        assert result[0].symbols == ["React"]
        assert result[0].is_relative is False

    def test_namespace_import(self, extractor: JavaScriptExtractor) -> None:
        content = "import * as utils from './utils';"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].symbols == ["utils"]

    def test_side_effect_import(self, extractor: JavaScriptExtractor) -> None:
        content = "import './styles.css';"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].symbols == []

    def test_mixed_import(self, extractor: JavaScriptExtractor) -> None:
        content = "import App, { render } from './app';"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert "App" in result[0].symbols
        assert "render" in result[0].symbols


# ---------------------------------------------------------------------------
# CommonJS Imports
# ---------------------------------------------------------------------------


class TestCommonJSImports:
    """Tests for CommonJS require extraction."""

    def test_require_default(self, extractor: JavaScriptExtractor) -> None:
        content = "const express = require('express');"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "express"
        assert result[0].symbols == ["express"]

    def test_require_destructured(self, extractor: JavaScriptExtractor) -> None:
        content = "const { Router, json } = require('express');"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "express"
        assert "Router" in result[0].symbols
        assert "json" in result[0].symbols

    def test_require_relative(self, extractor: JavaScriptExtractor) -> None:
        content = "const utils = require('./utils');"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].is_relative is True

    def test_bare_require(self, extractor: JavaScriptExtractor) -> None:
        content = "require('dotenv/config');"
        result = extractor.extract_imports(content)
        assert any(i.source == "dotenv/config" for i in result)


# ---------------------------------------------------------------------------
# ES Module Exports
# ---------------------------------------------------------------------------


class TestESExports:
    """Tests for ES module export extraction."""

    def test_export_function(self, extractor: JavaScriptExtractor) -> None:
        content = "export function handler() {}"
        result = extractor.extract_exports(content)
        assert result[0].name == "handler"
        assert result[0].kind == "function"

    def test_export_class(self, extractor: JavaScriptExtractor) -> None:
        content = "export class Service {}"
        result = extractor.extract_exports(content)
        assert result[0].name == "Service"
        assert result[0].kind == "class"

    def test_export_const(self, extractor: JavaScriptExtractor) -> None:
        content = "export const PORT = 3000;"
        result = extractor.extract_exports(content)
        assert result[0].name == "PORT"
        assert result[0].kind == "variable"

    def test_export_default_named(self, extractor: JavaScriptExtractor) -> None:
        content = "export default function main() {}"
        result = extractor.extract_exports(content)
        assert any(e.name == "main" and e.kind == "default" for e in result)

    def test_export_default_anonymous(self, extractor: JavaScriptExtractor) -> None:
        content = "export default function() {}"
        result = extractor.extract_exports(content)
        assert any(e.kind == "default" for e in result)

    def test_re_export(self, extractor: JavaScriptExtractor) -> None:
        content = "export { foo, bar };"
        result = extractor.extract_exports(content)
        names = {e.name for e in result}
        assert "foo" in names
        assert "bar" in names


# ---------------------------------------------------------------------------
# CommonJS Exports
# ---------------------------------------------------------------------------


class TestCommonJSExports:
    """Tests for CommonJS export extraction."""

    def test_module_exports_object(self, extractor: JavaScriptExtractor) -> None:
        content = "module.exports = { handler, router };"
        result = extractor.extract_exports(content)
        names = {e.name for e in result}
        assert "handler" in names
        assert "router" in names

    def test_module_exports_single(self, extractor: JavaScriptExtractor) -> None:
        content = "module.exports = app;"
        result = extractor.extract_exports(content)
        assert any(e.name == "app" and e.kind == "default" for e in result)

    def test_exports_prop(self, extractor: JavaScriptExtractor) -> None:
        content = "exports.handler = function() {};"
        result = extractor.extract_exports(content)
        assert any(e.name == "handler" for e in result)


# ---------------------------------------------------------------------------
# Test file detection
# ---------------------------------------------------------------------------


class TestDetectTestFile:
    """Tests for JavaScriptExtractor.detect_test_file()."""

    @pytest.mark.parametrize(
        "path",
        [
            "src/utils.test.js",
            "src/utils.spec.js",
            "src/App.test.jsx",
            "src/App.spec.jsx",
            "src/mod.test.mjs",
            "src/mod.spec.cjs",
        ],
    )
    def test_is_test_file(self, extractor: JavaScriptExtractor, path: str) -> None:
        assert extractor.detect_test_file(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "src/utils.js",
            "src/App.jsx",
            "src/test-helpers.js",
        ],
    )
    def test_not_test_file(self, extractor: JavaScriptExtractor, path: str) -> None:
        assert extractor.detect_test_file(path) is False
