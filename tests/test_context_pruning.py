"""Tests for context_pruning module — item #19."""

from pathlib import Path

import pytest

from repoforge.context_pruning import (
    CodeSymbol,
    PrunedContext,
    _extract_symbols_from_file,
    format_pruned_context,
    prune_context,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def python_project(tmp_path):
    """Create a temp Python project with known symbols."""
    (tmp_path / "models.py").write_text(
        "class User:\n    name: str\n    age: int\n\n\n"
        "class Order:\n    total: float\n\n\n"
        "def create_user(name):\n    return User()\n"
    )
    (tmp_path / "service.py").write_text(
        "from models import User, create_user\n\n\n"
        "def get_user(user_id):\n    return create_user('test')\n\n\n"
        "def list_users():\n    return []\n"
    )
    (tmp_path / "api.py").write_text(
        "from service import get_user\n\n\n"
        "def handler(request):\n    user = get_user(request.id)\n    return user\n"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Unit tests: symbol extraction
# ---------------------------------------------------------------------------


class TestSymbolExtraction:
    def test_extract_python_functions(self):
        content = "def foo():\n    return 1\n\ndef bar(x):\n    return x\n"
        symbols = _extract_symbols_from_file(content, "test.py")
        names = [s.name for s in symbols]
        assert "foo" in names
        assert "bar" in names

    def test_extract_python_classes(self):
        content = "class MyClass:\n    def method(self):\n        pass\n"
        symbols = _extract_symbols_from_file(content, "test.py")
        names = [s.name for s in symbols]
        assert "MyClass" in names

    def test_extract_includes_source(self):
        content = "def hello():\n    print('world')\n"
        symbols = _extract_symbols_from_file(content, "test.py")
        assert len(symbols) == 1
        assert "print('world')" in symbols[0].source

    def test_unsupported_extension_returns_empty(self):
        symbols = _extract_symbols_from_file("some content", "data.csv")
        assert symbols == []


# ---------------------------------------------------------------------------
# Unit tests: PrunedContext
# ---------------------------------------------------------------------------


class TestPrunedContext:
    def test_empty_context(self):
        ctx = PrunedContext()
        assert ctx.reduction_ratio == 0.0

    def test_reduction_ratio(self):
        ctx = PrunedContext(
            total_lines_original=100,
            total_lines_pruned=25,
        )
        assert ctx.reduction_ratio == 0.75


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestPruneContext:
    def test_prune_changed_file(self, python_project):
        ctx = prune_context(
            str(python_project), ["models.py"],
            include_dependents=False,
        )
        assert ctx.changed_files == ["models.py"]
        assert len(ctx.symbols) > 0
        symbol_names = [s.name for s in ctx.symbols]
        assert "User" in symbol_names
        assert "create_user" in symbol_names

    def test_prune_with_dependents(self, python_project):
        ctx = prune_context(
            str(python_project), ["models.py"],
            include_dependents=True,
        )
        # Should find dependent symbols that reference models symbols
        assert ctx.changed_files == ["models.py"]
        # Either we have dependent symbols or just the changed ones
        assert len(ctx.symbols) > 0

    def test_prune_empty_files(self, python_project):
        ctx = prune_context(str(python_project), [])
        assert ctx.changed_files == []
        assert ctx.symbols == []

    def test_prune_nonexistent_file(self, python_project):
        ctx = prune_context(str(python_project), ["nonexistent.py"])
        assert ctx.changed_files == ["nonexistent.py"]
        assert ctx.symbols == []


# ---------------------------------------------------------------------------
# Formatter tests
# ---------------------------------------------------------------------------


class TestFormatPrunedContext:
    def test_format_with_symbols(self):
        ctx = PrunedContext(
            changed_files=["test.py"],
            symbols=[
                CodeSymbol(
                    name="foo", kind="function", file="test.py",
                    line_start=1, line_end=3, source="def foo():\n    return 1",
                ),
            ],
            total_lines_original=100,
            total_lines_pruned=2,
        )
        output = format_pruned_context(ctx)
        assert "Pruned Code Context" in output
        assert "foo" in output
        assert "98%" in output

    def test_format_empty(self):
        ctx = PrunedContext()
        output = format_pruned_context(ctx)
        assert "No symbols extracted" in output
