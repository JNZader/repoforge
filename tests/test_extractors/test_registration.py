"""
tests/test_extractors/test_registration.py — Integration tests for extractor registration.

Tests cover:
- All 6 extractors are registered in the module-level registry
- get_extractor() returns the correct extractor for each language
- All expected extensions are supported
"""

import pytest

from repoforge.extractors import get_extractor, supported_extensions
from repoforge.extractors.go import GoExtractor
from repoforge.extractors.java import JavaExtractor
from repoforge.extractors.javascript import JavaScriptExtractor
from repoforge.extractors.python_ext import PythonExtractor
from repoforge.extractors.rust import RustExtractor
from repoforge.extractors.typescript import TypeScriptExtractor

# ---------------------------------------------------------------------------
# Registration verification
# ---------------------------------------------------------------------------


class TestAllExtractorsRegistered:
    """Verify all 6 language extractors are wired into the module registry."""

    @pytest.mark.parametrize(
        ("file_path", "expected_type"),
        [
            ("src/app.ts", TypeScriptExtractor),
            ("src/App.tsx", TypeScriptExtractor),
            ("src/index.js", JavaScriptExtractor),
            ("src/App.jsx", JavaScriptExtractor),
            ("src/utils.mjs", JavaScriptExtractor),
            ("src/config.cjs", JavaScriptExtractor),
            ("app/models.py", PythonExtractor),
            ("cmd/main.go", GoExtractor),
            ("src/Main.java", JavaExtractor),
            ("src/lib.rs", RustExtractor),
        ],
    )
    def test_get_extractor_returns_correct_type(
        self, file_path: str, expected_type: type
    ) -> None:
        ext = get_extractor(file_path)
        assert ext is not None, f"No extractor found for {file_path}"
        assert isinstance(ext, expected_type), (
            f"Expected {expected_type.__name__} for {file_path}, "
            f"got {type(ext).__name__}"
        )

    def test_all_expected_extensions_supported(self) -> None:
        exts = set(supported_extensions())
        expected = {
            ".ts", ".tsx",
            ".js", ".jsx", ".mjs", ".cjs",
            ".py",
            ".go",
            ".java",
            ".rs",
        }
        assert expected.issubset(exts), (
            f"Missing extensions: {expected - exts}"
        )

    def test_unknown_extension_returns_none(self) -> None:
        assert get_extractor("README.md") is None
        assert get_extractor("Makefile") is None
        assert get_extractor("styles.css") is None

    def test_six_languages_registered(self) -> None:
        """Verify at least 6 unique languages are registered."""
        exts = supported_extensions()
        # 10 extensions across 6 languages: .ts .tsx .js .jsx .mjs .cjs .py .go .java .rs
        assert len(exts) >= 10
