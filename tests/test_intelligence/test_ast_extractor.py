"""Tests for the AST extractor framework — base types and helpers."""

import pytest

from repoforge.intelligence.ast_extractor import (
    ASTSymbol,
    ASTLanguageExtractor,
    get_parser,
    parse_source,
    node_text,
    find_children,
    find_first_child,
)


class TestASTSymbol:
    """ASTSymbol dataclass behavior."""

    def test_basic_creation(self):
        sym = ASTSymbol(name="foo", kind="function", signature="func foo()")
        assert sym.name == "foo"
        assert sym.kind == "function"
        assert sym.signature == "func foo()"
        assert sym.params == []
        assert sym.return_type is None
        assert sym.docstring is None
        assert sym.decorators == []
        assert sym.fields == []
        assert sym.line == 0
        assert sym.file == ""

    def test_full_creation(self):
        sym = ASTSymbol(
            name="process",
            kind="method",
            signature="def process(data: list) -> dict",
            params=["data: list"],
            return_type="dict",
            docstring="Process data.",
            decorators=["@cache"],
            fields=[],
            line=42,
            file="src/utils.py",
        )
        assert sym.return_type == "dict"
        assert sym.line == 42
        assert sym.decorators == ["@cache"]

    def test_frozen(self):
        sym = ASTSymbol(name="x", kind="variable", signature="const x")
        with pytest.raises(AttributeError):
            sym.name = "y"


class TestGetParser:
    """get_parser() returns a parser or None."""

    def test_known_language(self):
        parser = get_parser("go")
        assert parser is not None

    def test_unknown_language(self):
        parser = get_parser("brainfuck_nonexistent_lang_xyz")
        assert parser is None


class TestParseSource:
    """parse_source() returns a root node or None."""

    def test_valid_go(self):
        parser = get_parser("go")
        root = parse_source(parser, "package main\nfunc main() {}")
        assert root is not None
        assert root.type == "source_file"

    def test_none_parser(self):
        root = parse_source(None, "anything")
        assert root is None


class TestNodeHelpers:
    """node_text, find_children, find_first_child."""

    def test_node_text(self):
        parser = get_parser("go")
        root = parse_source(parser, "package main")
        assert "main" in node_text(root)

    def test_node_text_none(self):
        assert node_text(None) == ""

    def test_find_children(self):
        parser = get_parser("go")
        root = parse_source(parser, "package main\nfunc Foo() {}\nfunc Bar() {}")
        funcs = find_children(root, "function_declaration")
        assert len(funcs) == 2

    def test_find_first_child(self):
        parser = get_parser("go")
        root = parse_source(parser, "package main\nfunc Foo() {}")
        func = find_first_child(root, "function_declaration")
        assert func is not None
        assert func.type == "function_declaration"

    def test_find_first_child_missing(self):
        parser = get_parser("go")
        root = parse_source(parser, "package main")
        result = find_first_child(root, "class_declaration")
        assert result is None
