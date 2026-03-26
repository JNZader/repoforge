"""
tests/test_extractors/test_python_ext.py — Tests for PythonExtractor.

Tests cover:
- from x import y, z
- import x
- Relative imports (from . import, from .. import)
- __all__ export lists
- Public function/class exports
- Top-level constant exports
- Private members excluded
- Test file detection
"""

import pytest

from repoforge.extractors.python_ext import PythonExtractor


@pytest.fixture
def extractor() -> PythonExtractor:
    return PythonExtractor()


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------


class TestExtractImports:
    """Tests for PythonExtractor.extract_imports()."""

    def test_from_import(self, extractor: PythonExtractor) -> None:
        content = "from os.path import join, exists"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "os.path"
        assert result[0].symbols == ["join", "exists"]
        assert result[0].is_relative is False

    def test_import_module(self, extractor: PythonExtractor) -> None:
        content = "import os"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "os"
        assert result[0].symbols == []

    def test_import_multiple_modules(self, extractor: PythonExtractor) -> None:
        content = "import os, sys"
        result = extractor.extract_imports(content)
        assert len(result) == 2
        sources = {i.source for i in result}
        assert sources == {"os", "sys"}

    def test_relative_import_dot(self, extractor: PythonExtractor) -> None:
        content = "from . import utils"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "."
        assert result[0].symbols == ["utils"]
        assert result[0].is_relative is True

    def test_relative_import_dotdot(self, extractor: PythonExtractor) -> None:
        content = "from ..models import User"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "..models"
        assert result[0].is_relative is True

    def test_import_with_alias(self, extractor: PythonExtractor) -> None:
        content = "from typing import List as L"
        result = extractor.extract_imports(content)
        assert result[0].symbols == ["List"]

    def test_import_module_alias(self, extractor: PythonExtractor) -> None:
        content = "import numpy as np"
        result = extractor.extract_imports(content)
        assert result[0].source == "numpy"

    def test_from_import_with_parens(self, extractor: PythonExtractor) -> None:
        content = "from typing import (Dict, List, Optional)"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert "Dict" in result[0].symbols
        assert "List" in result[0].symbols
        assert "Optional" in result[0].symbols

    def test_wildcard_import_excluded(self, extractor: PythonExtractor) -> None:
        content = "from os.path import *"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].symbols == []


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


class TestExtractExports:
    """Tests for PythonExtractor.extract_exports()."""

    def test_public_function(self, extractor: PythonExtractor) -> None:
        content = "def handle_request():\n    pass"
        result = extractor.extract_exports(content)
        assert any(e.name == "handle_request" and e.kind == "function" for e in result)

    def test_private_function_excluded(self, extractor: PythonExtractor) -> None:
        content = "def _internal():\n    pass"
        result = extractor.extract_exports(content)
        assert not any(e.name == "_internal" for e in result)

    def test_public_class(self, extractor: PythonExtractor) -> None:
        content = "class UserService:\n    pass"
        result = extractor.extract_exports(content)
        assert any(e.name == "UserService" and e.kind == "class" for e in result)

    def test_private_class_excluded(self, extractor: PythonExtractor) -> None:
        content = "class _Internal:\n    pass"
        result = extractor.extract_exports(content)
        assert not any(e.name == "_Internal" for e in result)

    def test_top_level_constant(self, extractor: PythonExtractor) -> None:
        content = "MAX_RETRIES = 3"
        result = extractor.extract_exports(content)
        assert any(e.name == "MAX_RETRIES" and e.kind == "variable" for e in result)

    def test_all_list_overrides(self, extractor: PythonExtractor) -> None:
        content = """
__all__ = ['foo', 'Bar']

def foo():
    pass

class Bar:
    pass

def baz():
    pass
"""
        result = extractor.extract_exports(content)
        names = {e.name for e in result}
        assert names == {"foo", "Bar"}

    def test_multiple_exports(self, extractor: PythonExtractor) -> None:
        content = """
def public_func():
    pass

class PublicClass:
    pass

MAX_SIZE = 100

def _private():
    pass
"""
        result = extractor.extract_exports(content)
        names = {e.name for e in result}
        assert "public_func" in names
        assert "PublicClass" in names
        assert "MAX_SIZE" in names
        assert "_private" not in names


# ---------------------------------------------------------------------------
# Test file detection
# ---------------------------------------------------------------------------


class TestDetectTestFile:
    """Tests for PythonExtractor.detect_test_file()."""

    @pytest.mark.parametrize(
        "path",
        [
            "tests/test_utils.py",
            "tests/test_models.py",
            "src/utils_test.py",
        ],
    )
    def test_is_test_file(self, extractor: PythonExtractor, path: str) -> None:
        assert extractor.detect_test_file(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "src/utils.py",
            "src/models.py",
            "src/testing.py",
            "conftest.py",
        ],
    )
    def test_not_test_file(self, extractor: PythonExtractor, path: str) -> None:
        assert extractor.detect_test_file(path) is False
