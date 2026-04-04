"""Tests for the AST extractor registry — wiring and tiered extraction."""

import pytest

from repoforge.intelligence.ast_extractor import ASTSymbol
from repoforge.intelligence.extractor_registry import (
    ASTExtractorRegistry,
    ast_extract_endpoints,
    ast_extract_schemas,
    ast_extract_symbols,
    get_ast_registry,
)


class TestASTExtractorRegistry:
    """Registry maps extensions to extractors."""

    def test_get_ast_registry(self):
        """Registry should initialize when tree-sitter is available."""
        reg = get_ast_registry()
        assert reg is not None
        assert len(reg) > 0

    def test_supported_extensions(self):
        reg = get_ast_registry()
        exts = reg.supported_extensions()
        assert ".go" in exts
        assert ".py" in exts
        assert ".ts" in exts
        assert ".tsx" in exts
        assert ".js" in exts
        assert ".java" in exts
        assert ".rs" in exts

    def test_get_for_file_go(self):
        reg = get_ast_registry()
        ext = reg.get_for_file("server.go")
        assert ext is not None
        assert ext.language_name == "go"

    def test_get_for_file_python(self):
        reg = get_ast_registry()
        ext = reg.get_for_file("models.py")
        assert ext is not None
        assert ext.language_name == "python"

    def test_get_for_file_unknown(self):
        reg = get_ast_registry()
        ext = reg.get_for_file("file.xyz")
        assert ext is None

    def test_extract_symbols_unknown_ext(self):
        reg = get_ast_registry()
        symbols = reg.extract_symbols("anything", "file.xyz")
        assert symbols == []


class TestConvenienceFunctions:
    """Module-level convenience functions."""

    def test_ast_extract_symbols(self):
        symbols = ast_extract_symbols(
            'package main\nfunc Hello() {}',
            "hello.go",
        )
        assert len(symbols) >= 1
        assert any(s.name == "Hello" for s in symbols)

    def test_ast_extract_endpoints(self):
        endpoints = ast_extract_endpoints(
            '''package main
func routes() {
    mux.HandleFunc("GET /health", h)
}''',
            "routes.go",
        )
        assert len(endpoints) >= 1

    def test_ast_extract_schemas(self):
        schemas = ast_extract_schemas(
            '''class User(BaseModel):
    name: str
''',
            "models.py",
        )
        assert len(schemas) >= 1

    def test_unknown_extension_returns_empty(self):
        assert ast_extract_symbols("data", "file.txt") == []
        assert ast_extract_endpoints("data", "file.txt") == []
        assert ast_extract_schemas("data", "file.txt") == []


class TestTieredExtraction:
    """Verify extraction works across different languages."""

    @pytest.mark.parametrize("code,path,expected_name", [
        ("package main\nfunc Foo() {}", "foo.go", "Foo"),
        ("def bar(): pass", "bar.py", "bar"),
        ("export function baz() {}", "baz.ts", "baz"),
        ("export function qux() {}", "qux.js", "qux"),
        ("pub fn quux() {}", "quux.rs", "quux"),
    ])
    def test_cross_language_symbols(self, code, path, expected_name):
        symbols = ast_extract_symbols(code, path)
        names = {s.name for s in symbols}
        assert expected_name in names
