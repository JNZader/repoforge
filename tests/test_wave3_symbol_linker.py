"""Tests for Wave 3: Cross-file symbol linking."""

import pytest
from repoforge.intelligence.ast_extractor import ASTSymbol
from repoforge.intelligence.symbol_linker import SymbolLinker


def _sym(name, kind="class", file="a.py", signature="", fields=None, params=None, line=1):
    """Helper to create ASTSymbol with minimal boilerplate."""
    return ASTSymbol(
        name=name, kind=kind, signature=signature or f"{kind} {name}",
        file=file, line=line, fields=fields or [], params=params or [],
    )


class TestSymbolLinkerBasics:

    def test_empty_symbols(self):
        linker = SymbolLinker({})
        assert linker.resolve_type("Foo") is None

    def test_resolve_type_by_name(self):
        symbols = {
            "models.py": [_sym("User", kind="class", file="models.py")],
        }
        linker = SymbolLinker(symbols)
        result = linker.resolve_type("User")
        assert result is not None
        assert result.name == "User"
        assert result.file == "models.py"

    def test_resolve_returns_none_for_unknown(self):
        symbols = {"a.py": [_sym("Foo", file="a.py")]}
        linker = SymbolLinker(symbols)
        assert linker.resolve_type("Bar") is None

    def test_resolve_prioritizes_class_over_function(self):
        symbols = {
            "a.py": [
                _sym("User", kind="function", file="a.py"),
                _sym("User", kind="class", file="a.py"),
            ],
        }
        linker = SymbolLinker(symbols)
        result = linker.resolve_type("User")
        assert result.kind == "class"


class TestInheritanceExtraction:

    def test_extract_extends_from_signature(self):
        symbols = {
            "base.py": [_sym("BaseService", kind="class", file="base.py")],
            "user.py": [_sym("UserService", kind="class", file="user.py",
                             signature="class UserService extends BaseService")],
        }
        linker = SymbolLinker(symbols)
        parents = linker.get_parents("UserService")
        assert "BaseService" in parents

    def test_extract_implements_from_signature(self):
        symbols = {
            "iface.java": [_sym("Serializable", kind="interface", file="iface.java")],
            "user.java": [_sym("User", kind="class", file="user.java",
                               signature="class User implements Serializable, Comparable")],
        }
        linker = SymbolLinker(symbols)
        parents = linker.get_parents("User")
        assert "Serializable" in parents
        assert "Comparable" in parents

    def test_no_parents_when_no_extends(self):
        symbols = {"a.py": [_sym("Foo", kind="class", file="a.py", signature="class Foo")]}
        linker = SymbolLinker(symbols)
        assert linker.get_parents("Foo") == []

    def test_python_parenthesis_inheritance(self):
        symbols = {
            "base.py": [_sym("Base", kind="class", file="base.py")],
            "child.py": [_sym("Child", kind="class", file="child.py",
                              signature="class Child(Base, Mixin)")],
        }
        linker = SymbolLinker(symbols)
        parents = linker.get_parents("Child")
        assert "Base" in parents
        assert "Mixin" in parents


class TestGetImplementors:

    def test_find_implementors(self):
        symbols = {
            "iface.go": [_sym("Store", kind="interface", file="iface.go")],
            "sqlite.go": [_sym("SQLiteStore", kind="struct", file="sqlite.go",
                               signature="struct SQLiteStore implements Store")],
            "mem.go": [_sym("MemStore", kind="struct", file="mem.go",
                            signature="struct MemStore implements Store")],
        }
        linker = SymbolLinker(symbols)
        impls = linker.get_implementors("Store")
        names = [s.name for s in impls]
        assert "SQLiteStore" in names
        assert "MemStore" in names

    def test_no_implementors(self):
        symbols = {"a.py": [_sym("Foo", kind="interface", file="a.py")]}
        linker = SymbolLinker(symbols)
        assert linker.get_implementors("Foo") == []


class TestGetUsages:

    def test_find_type_usage_in_params(self):
        symbols = {
            "types.py": [_sym("Config", kind="class", file="types.py")],
            "app.py": [_sym("start", kind="function", file="app.py",
                            signature="def start(config: Config) -> None",
                            params=["config: Config"])],
        }
        linker = SymbolLinker(symbols)
        usages = linker.get_usages("Config")
        assert any(s.name == "start" for s in usages)

    def test_find_type_usage_in_return_type(self):
        symbols = {
            "types.py": [_sym("User", kind="class", file="types.py")],
            "repo.py": [ASTSymbol(
                name="get_user", kind="function", file="repo.py",
                signature="def get_user(id: int) -> User",
                return_type="User", line=10,
            )],
        }
        linker = SymbolLinker(symbols)
        usages = linker.get_usages("User")
        assert any(s.name == "get_user" for s in usages)


class TestFormatContext:

    def test_format_type_context(self):
        symbols = {
            "base.py": [_sym("BaseModel", kind="class", file="base.py",
                             fields=["id: int", "created_at: datetime"])],
            "user.py": [_sym("User", kind="class", file="user.py",
                             signature="class User(BaseModel)",
                             fields=["name: str", "email: str"])],
        }
        linker = SymbolLinker(symbols)
        ctx = linker.format_type_context("User")
        assert "User" in ctx
        assert "BaseModel" in ctx
        assert "base.py" in ctx

    def test_format_unknown_type_returns_empty(self):
        linker = SymbolLinker({})
        assert linker.format_type_context("Unknown") == ""


# ── chunk_type_relationships integration ─────────────────────────────────


class TestChunkTypeRelationships:

    def test_empty_symbols_returns_empty(self):
        from repoforge.intelligence.doc_chunks import chunk_type_relationships
        assert chunk_type_relationships({}) == ""

    def test_no_relationships_returns_empty(self):
        from repoforge.intelligence.doc_chunks import chunk_type_relationships
        symbols = {"a.py": [_sym("Foo", kind="class", file="a.py")]}
        # Single class with no inheritance, no usages → no relationships section
        result = chunk_type_relationships(symbols)
        # May return empty or just header — either is fine
        assert "Inheritance" not in result

    def test_shows_inheritance(self):
        from repoforge.intelligence.doc_chunks import chunk_type_relationships
        symbols = {
            "base.py": [_sym("Base", kind="class", file="base.py")],
            "child.py": [_sym("Child", kind="class", file="child.py",
                              signature="class Child(Base)")],
        }
        result = chunk_type_relationships(symbols)
        assert "Inheritance" in result
        assert "Child" in result
        assert "Base" in result

    def test_shows_implementations(self):
        from repoforge.intelligence.doc_chunks import chunk_type_relationships
        symbols = {
            "iface.go": [_sym("Store", kind="interface", file="iface.go")],
            "impl.go": [_sym("SQLStore", kind="struct", file="impl.go",
                             signature="struct SQLStore implements Store")],
        }
        result = chunk_type_relationships(symbols)
        assert "Implementations" in result
        assert "SQLStore" in result
