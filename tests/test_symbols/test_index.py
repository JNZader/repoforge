"""Tests for SymbolIndex — construction, lookups, resolve, and edge cases."""

import pytest

from repoforge.symbols.extractor import Symbol
from repoforge.symbols.index import SymbolIndex

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sym(name: str, file: str, kind: str = "function", line: int = 1) -> Symbol:
    """Helper to create a Symbol with minimal boilerplate."""
    return Symbol(name=name, kind=kind, file=file, line=line, end_line=line + 5)


@pytest.fixture()
def sample_symbols() -> list[Symbol]:
    """A realistic set of symbols across multiple files."""
    return [
        _sym("process_data", "src/pipeline.py", line=10),
        _sym("validate", "src/pipeline.py", line=25),
        _sym("validate", "src/utils.py", line=5),
        _sym("DataLoader", "src/pipeline.py", kind="class", line=40),
        _sym("format_output", "src/utils.py", line=20),
        _sym("main", "src/cli.py", line=1),
    ]


@pytest.fixture()
def index(sample_symbols: list[Symbol]) -> SymbolIndex:
    return SymbolIndex.from_symbols(sample_symbols)


# ---------------------------------------------------------------------------
# Task 1.3 — Construction tests
# ---------------------------------------------------------------------------


class TestConstruction:

    def test_from_symbols_creates_index(self, index: SymbolIndex) -> None:
        assert index.symbol_count == 6
        assert index.file_count == 3

    def test_empty_list(self) -> None:
        idx = SymbolIndex.from_symbols([])
        assert idx.symbol_count == 0
        assert idx.file_count == 0

    def test_single_symbol(self) -> None:
        idx = SymbolIndex.from_symbols([_sym("foo", "a.py")])
        assert idx.symbol_count == 1
        assert idx.file_count == 1


# ---------------------------------------------------------------------------
# Task 1.3 — Lookup by name
# ---------------------------------------------------------------------------


class TestByName:

    def test_unique_name(self, index: SymbolIndex) -> None:
        results = index.by_name("process_data")
        assert len(results) == 1
        assert results[0].file == "src/pipeline.py"

    def test_duplicate_name_returns_all(self, index: SymbolIndex) -> None:
        results = index.by_name("validate")
        assert len(results) == 2
        files = {s.file for s in results}
        assert files == {"src/pipeline.py", "src/utils.py"}

    def test_missing_name(self, index: SymbolIndex) -> None:
        assert index.by_name("nonexistent") == []


# ---------------------------------------------------------------------------
# Task 1.3 — Lookup by qualified name
# ---------------------------------------------------------------------------


class TestByQualified:

    def test_exact_match(self, index: SymbolIndex) -> None:
        sym = index.by_qualified("src/pipeline.py", "process_data")
        assert sym is not None
        assert sym.name == "process_data"
        assert sym.file == "src/pipeline.py"

    def test_disambiguates_duplicates(self, index: SymbolIndex) -> None:
        sym1 = index.by_qualified("src/pipeline.py", "validate")
        sym2 = index.by_qualified("src/utils.py", "validate")
        assert sym1 is not None and sym2 is not None
        assert sym1.file == "src/pipeline.py"
        assert sym2.file == "src/utils.py"

    def test_wrong_file(self, index: SymbolIndex) -> None:
        assert index.by_qualified("src/cli.py", "validate") is None

    def test_wrong_name(self, index: SymbolIndex) -> None:
        assert index.by_qualified("src/pipeline.py", "nonexistent") is None


# ---------------------------------------------------------------------------
# Task 1.3 — Lookup by file
# ---------------------------------------------------------------------------


class TestByFile:

    def test_returns_all_in_file(self, index: SymbolIndex) -> None:
        results = index.by_file("src/pipeline.py")
        assert len(results) == 3
        names = {s.name for s in results}
        assert names == {"process_data", "validate", "DataLoader"}

    def test_single_symbol_file(self, index: SymbolIndex) -> None:
        results = index.by_file("src/cli.py")
        assert len(results) == 1
        assert results[0].name == "main"

    def test_missing_file(self, index: SymbolIndex) -> None:
        assert index.by_file("nonexistent.py") == []


# ---------------------------------------------------------------------------
# Task 1.3 — Resolve with various scenarios
# ---------------------------------------------------------------------------


class TestResolve:

    def test_same_file_match(self, index: SymbolIndex) -> None:
        """Resolve prefers same-file symbol."""
        sym = index.resolve("validate", from_file="src/pipeline.py")
        assert sym is not None
        assert sym.file == "src/pipeline.py"

    def test_import_based_match(self, index: SymbolIndex) -> None:
        """Resolve uses imports dict when same-file fails."""
        sym = index.resolve(
            "validate",
            from_file="src/cli.py",
            imports={"validate": "src/utils.py"},
        )
        assert sym is not None
        assert sym.file == "src/utils.py"

    def test_unique_global_match(self, index: SymbolIndex) -> None:
        """Resolve falls back to unique global name."""
        sym = index.resolve("format_output", from_file="src/cli.py")
        assert sym is not None
        assert sym.name == "format_output"
        assert sym.file == "src/utils.py"

    def test_ambiguous_returns_none(self, index: SymbolIndex) -> None:
        """Resolve returns None when name is ambiguous and no import/same-file."""
        sym = index.resolve("validate", from_file="src/cli.py")
        assert sym is None

    def test_not_found_returns_none(self, index: SymbolIndex) -> None:
        sym = index.resolve("nonexistent", from_file="src/cli.py")
        assert sym is None

    def test_resolve_no_imports_dict(self, index: SymbolIndex) -> None:
        """Resolve works when imports is None (default)."""
        sym = index.resolve("main", from_file="src/pipeline.py")
        assert sym is not None
        assert sym.name == "main"

    def test_resolve_import_target_missing(self, index: SymbolIndex) -> None:
        """Import points to a file that doesn't have the symbol."""
        sym = index.resolve(
            "validate",
            from_file="src/cli.py",
            imports={"validate": "src/nonexistent.py"},
        )
        # Falls through to global — ambiguous, returns None
        assert sym is None


# ---------------------------------------------------------------------------
# Task 1.3 — Empty index
# ---------------------------------------------------------------------------


class TestEmptyIndex:

    def test_by_name_empty(self) -> None:
        idx = SymbolIndex.from_symbols([])
        assert idx.by_name("anything") == []

    def test_by_qualified_empty(self) -> None:
        idx = SymbolIndex.from_symbols([])
        assert idx.by_qualified("a.py", "foo") is None

    def test_by_file_empty(self) -> None:
        idx = SymbolIndex.from_symbols([])
        assert idx.by_file("a.py") == []

    def test_resolve_empty(self) -> None:
        idx = SymbolIndex.from_symbols([])
        assert idx.resolve("foo", from_file="a.py") is None

    def test_properties_empty(self) -> None:
        idx = SymbolIndex.from_symbols([])
        assert idx.symbol_count == 0
        assert idx.file_count == 0


# ---------------------------------------------------------------------------
# Task 1.4 — Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:

    def test_duplicate_names_across_files(self) -> None:
        """Same function name in 3 different files."""
        symbols = [
            _sym("helper", "a.py"),
            _sym("helper", "b.py"),
            _sym("helper", "c.py"),
        ]
        idx = SymbolIndex.from_symbols(symbols)
        assert len(idx.by_name("helper")) == 3
        assert idx.symbol_count == 3

    def test_duplicate_names_resolve_same_file(self) -> None:
        """Resolve picks the same-file version even with duplicates."""
        symbols = [
            _sym("run", "a.py"),
            _sym("run", "b.py"),
            _sym("run", "c.py"),
        ]
        idx = SymbolIndex.from_symbols(symbols)
        sym = idx.resolve("run", from_file="b.py")
        assert sym is not None
        assert sym.file == "b.py"

    def test_duplicate_names_resolve_via_import(self) -> None:
        """Resolve picks the imported version when not in same file."""
        symbols = [
            _sym("run", "a.py"),
            _sym("run", "b.py"),
        ]
        idx = SymbolIndex.from_symbols(symbols)
        sym = idx.resolve("run", from_file="c.py", imports={"run": "a.py"})
        assert sym is not None
        assert sym.file == "a.py"

    def test_qualified_lookup_no_match(self) -> None:
        """Qualified lookup returns None for valid file but wrong name."""
        idx = SymbolIndex.from_symbols([_sym("foo", "a.py")])
        assert idx.by_qualified("a.py", "bar") is None

    def test_qualified_lookup_wrong_file(self) -> None:
        """Qualified lookup returns None for wrong file but valid name."""
        idx = SymbolIndex.from_symbols([_sym("foo", "a.py")])
        assert idx.by_qualified("b.py", "foo") is None

    def test_class_and_function_same_name(self) -> None:
        """A class and function with the same name in different files."""
        symbols = [
            _sym("Config", "config.py", kind="class"),
            _sym("Config", "factory.py", kind="function"),
        ]
        idx = SymbolIndex.from_symbols(symbols)
        assert len(idx.by_name("Config")) == 2
        assert idx.by_qualified("config.py", "Config") is not None
        assert idx.by_qualified("config.py", "Config").kind == "class"
        assert idx.by_qualified("factory.py", "Config").kind == "function"

    def test_many_symbols_in_one_file(self) -> None:
        """Index handles a file with many symbols."""
        symbols = [_sym(f"func_{i}", "big.py", line=i * 10) for i in range(100)]
        idx = SymbolIndex.from_symbols(symbols)
        assert idx.file_count == 1
        assert idx.symbol_count == 100
        assert len(idx.by_file("big.py")) == 100

    def test_resolve_unique_global_from_different_file(self) -> None:
        """Unique global resolution works when called from any file."""
        symbols = [
            _sym("unique_fn", "lib.py"),
            _sym("other", "main.py"),
        ]
        idx = SymbolIndex.from_symbols(symbols)
        sym = idx.resolve("unique_fn", from_file="main.py")
        assert sym is not None
        assert sym.file == "lib.py"

    def test_resolve_ambiguous_no_same_file_no_import(self) -> None:
        """Multiple definitions, no same-file, no import -> None."""
        symbols = [
            _sym("helper", "a.py"),
            _sym("helper", "b.py"),
        ]
        idx = SymbolIndex.from_symbols(symbols)
        assert idx.resolve("helper", from_file="c.py") is None

    def test_from_symbols_preserves_order(self) -> None:
        """by_file returns symbols in insertion order."""
        s1 = _sym("alpha", "x.py", line=1)
        s2 = _sym("beta", "x.py", line=10)
        s3 = _sym("gamma", "x.py", line=20)
        idx = SymbolIndex.from_symbols([s1, s2, s3])
        names = [s.name for s in idx.by_file("x.py")]
        assert names == ["alpha", "beta", "gamma"]
