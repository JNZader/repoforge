"""
tests/test_extractors/test_registry.py — Tests for the ExtractorRegistry.

Tests cover:
- Registering extractors and looking them up by file path
- Multiple extensions per extractor
- Unknown extensions return None
- supported_extensions() listing
- Overwrite behavior (last-write-wins)
- len() and __contains__
"""

import pytest

from repoforge.extractors.registry import ExtractorRegistry
from repoforge.extractors.types import ExportInfo, ImportInfo

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class FakeExtractor:
    """Minimal extractor for testing the registry."""

    def __init__(self, language: str, extensions: list[str]) -> None:
        self.language = language
        self.extensions = extensions

    def extract_imports(self, content: str) -> list[ImportInfo]:
        return []

    def extract_exports(self, content: str) -> list[ExportInfo]:
        return []

    def detect_test_file(self, file_path: str) -> bool:
        return False


@pytest.fixture
def registry() -> ExtractorRegistry:
    return ExtractorRegistry()


@pytest.fixture
def ts_extractor() -> FakeExtractor:
    return FakeExtractor("typescript", [".ts", ".tsx"])


@pytest.fixture
def py_extractor() -> FakeExtractor:
    return FakeExtractor("python", [".py"])


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegister:
    """Tests for ExtractorRegistry.register()."""

    def test_register_single_extension(
        self, registry: ExtractorRegistry, py_extractor: FakeExtractor
    ) -> None:
        registry.register(py_extractor)
        result = registry.get_for_file("app/models.py")
        assert result is py_extractor

    def test_register_multiple_extensions(
        self, registry: ExtractorRegistry, ts_extractor: FakeExtractor
    ) -> None:
        registry.register(ts_extractor)
        assert registry.get_for_file("src/app.ts") is ts_extractor
        assert registry.get_for_file("src/App.tsx") is ts_extractor

    def test_register_normalizes_dot_prefix(
        self, registry: ExtractorRegistry
    ) -> None:
        ext = FakeExtractor("go", ["go"])  # no dot
        registry.register(ext)
        assert registry.get_for_file("main.go") is ext

    def test_overwrite_last_wins(self, registry: ExtractorRegistry) -> None:
        first = FakeExtractor("old", [".ts"])
        second = FakeExtractor("new", [".ts"])
        registry.register(first)
        registry.register(second)
        assert registry.get_for_file("file.ts") is second


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


class TestGetForFile:
    """Tests for ExtractorRegistry.get_for_file()."""

    def test_unknown_extension_returns_none(
        self, registry: ExtractorRegistry
    ) -> None:
        assert registry.get_for_file("README.md") is None

    def test_no_extension_returns_none(
        self, registry: ExtractorRegistry
    ) -> None:
        assert registry.get_for_file("Makefile") is None

    def test_nested_path(
        self, registry: ExtractorRegistry, py_extractor: FakeExtractor
    ) -> None:
        registry.register(py_extractor)
        assert registry.get_for_file("src/deep/nested/file.py") is py_extractor


# ---------------------------------------------------------------------------
# Utility methods
# ---------------------------------------------------------------------------


class TestUtilities:
    """Tests for supported_extensions, len, contains."""

    def test_supported_extensions_empty(
        self, registry: ExtractorRegistry
    ) -> None:
        assert registry.supported_extensions() == []

    def test_supported_extensions_sorted(
        self, registry: ExtractorRegistry,
        ts_extractor: FakeExtractor,
        py_extractor: FakeExtractor,
    ) -> None:
        registry.register(ts_extractor)
        registry.register(py_extractor)
        exts = registry.supported_extensions()
        assert exts == [".py", ".ts", ".tsx"]

    def test_len(
        self, registry: ExtractorRegistry, ts_extractor: FakeExtractor
    ) -> None:
        assert len(registry) == 0
        registry.register(ts_extractor)
        assert len(registry) == 2  # .ts and .tsx

    def test_contains(
        self, registry: ExtractorRegistry, py_extractor: FakeExtractor
    ) -> None:
        registry.register(py_extractor)
        assert ".py" in registry
        assert "py" in registry  # without dot
        assert ".rs" not in registry
