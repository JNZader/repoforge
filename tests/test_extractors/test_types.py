"""
tests/test_extractors/test_types.py — Tests for extractor data types.

Tests cover:
- ImportInfo creation with defaults and explicit values
- ExportInfo creation with defaults and explicit values
- Frozen dataclass immutability
- Extractor Protocol runtime checkability
"""

import pytest

from repoforge.extractors.types import ExportInfo, Extractor, ImportInfo

# ---------------------------------------------------------------------------
# ImportInfo
# ---------------------------------------------------------------------------


class TestImportInfo:
    """Tests for the ImportInfo dataclass."""

    def test_create_with_defaults(self) -> None:
        info = ImportInfo(source="lodash")
        assert info.source == "lodash"
        assert info.symbols == []
        assert info.is_relative is False

    def test_create_with_symbols(self) -> None:
        info = ImportInfo(source="./utils", symbols=["foo", "bar"], is_relative=True)
        assert info.source == "./utils"
        assert info.symbols == ["foo", "bar"]
        assert info.is_relative is True

    def test_create_relative_import(self) -> None:
        info = ImportInfo(source="../models", symbols=["User"], is_relative=True)
        assert info.is_relative is True
        assert info.source == "../models"

    def test_create_namespace_import(self) -> None:
        info = ImportInfo(source="fmt", symbols=[])
        assert info.symbols == []

    def test_frozen_immutability(self) -> None:
        info = ImportInfo(source="os")
        with pytest.raises(AttributeError):
            info.source = "sys"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = ImportInfo(source="fmt", symbols=[], is_relative=False)
        b = ImportInfo(source="fmt", symbols=[], is_relative=False)
        assert a == b

    def test_inequality(self) -> None:
        a = ImportInfo(source="fmt")
        b = ImportInfo(source="os")
        assert a != b


# ---------------------------------------------------------------------------
# ExportInfo
# ---------------------------------------------------------------------------


class TestExportInfo:
    """Tests for the ExportInfo dataclass."""

    def test_create_with_defaults(self) -> None:
        info = ExportInfo(name="MyClass")
        assert info.name == "MyClass"
        assert info.kind == "variable"

    def test_create_function_export(self) -> None:
        info = ExportInfo(name="process", kind="function")
        assert info.name == "process"
        assert info.kind == "function"

    def test_create_class_export(self) -> None:
        info = ExportInfo(name="UserService", kind="class")
        assert info.kind == "class"

    def test_create_type_export(self) -> None:
        info = ExportInfo(name="Config", kind="type")
        assert info.kind == "type"

    def test_create_default_export(self) -> None:
        info = ExportInfo(name="default", kind="default")
        assert info.kind == "default"

    def test_create_interface_export(self) -> None:
        info = ExportInfo(name="Serializable", kind="interface")
        assert info.kind == "interface"

    def test_frozen_immutability(self) -> None:
        info = ExportInfo(name="Foo")
        with pytest.raises(AttributeError):
            info.name = "Bar"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = ExportInfo(name="Foo", kind="class")
        b = ExportInfo(name="Foo", kind="class")
        assert a == b


# ---------------------------------------------------------------------------
# Extractor Protocol
# ---------------------------------------------------------------------------


class TestExtractorProtocol:
    """Tests for the Extractor Protocol runtime checkability."""

    def test_conforming_class_is_extractor(self) -> None:
        """A class with the right shape satisfies the Protocol."""

        class FakeExtractor:
            language = "fake"
            extensions = [".fake"]

            def extract_imports(self, content: str) -> list[ImportInfo]:
                return []

            def extract_exports(self, content: str) -> list[ExportInfo]:
                return []

            def detect_test_file(self, file_path: str) -> bool:
                return False

        assert isinstance(FakeExtractor(), Extractor)

    def test_non_conforming_class_is_not_extractor(self) -> None:
        """A class missing methods does NOT satisfy the Protocol."""

        class NotAnExtractor:
            language = "broken"

        assert not isinstance(NotAnExtractor(), Extractor)

    def test_missing_detect_test_file_is_not_extractor(self) -> None:
        """Missing detect_test_file should fail the protocol check."""

        class Partial:
            language = "partial"
            extensions = [".p"]

            def extract_imports(self, content: str) -> list[ImportInfo]:
                return []

            def extract_exports(self, content: str) -> list[ExportInfo]:
                return []

        assert not isinstance(Partial(), Extractor)
