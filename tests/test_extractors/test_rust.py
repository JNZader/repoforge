"""
tests/test_extractors/test_rust.py — Tests for RustExtractor.

Tests cover:
- use statements (single, grouped, glob)
- mod declarations
- crate/super relative imports
- pub fn, pub struct, pub enum, pub trait, pub type, pub const/static, pub mod
- pub(crate) visibility
- Test file detection (_test.rs, #[cfg(test)])
"""

import pytest

from repoforge.extractors.rust import RustExtractor


@pytest.fixture
def extractor() -> RustExtractor:
    return RustExtractor()


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------


class TestExtractImports:
    """Tests for RustExtractor.extract_imports()."""

    def test_single_use(self, extractor: RustExtractor) -> None:
        content = "use std::collections::HashMap;"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "std::collections"
        assert result[0].symbols == ["HashMap"]

    def test_grouped_use(self, extractor: RustExtractor) -> None:
        content = "use std::{io, fs};"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "std"
        assert "io" in result[0].symbols
        assert "fs" in result[0].symbols

    def test_glob_use(self, extractor: RustExtractor) -> None:
        content = "use std::io::prelude::*;"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "std::io::prelude"
        assert result[0].symbols == []

    def test_crate_import_is_relative(self, extractor: RustExtractor) -> None:
        content = "use crate::models::User;"
        result = extractor.extract_imports(content)
        assert result[0].is_relative is True

    def test_super_import_is_relative(self, extractor: RustExtractor) -> None:
        content = "use super::utils::helper;"
        result = extractor.extract_imports(content)
        assert result[0].is_relative is True

    def test_external_import_not_relative(self, extractor: RustExtractor) -> None:
        content = "use serde::Deserialize;"
        result = extractor.extract_imports(content)
        assert result[0].is_relative is False

    def test_mod_declaration(self, extractor: RustExtractor) -> None:
        content = "mod handlers;"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "handlers"
        assert result[0].symbols == []
        assert result[0].is_relative is True

    def test_pub_mod_declaration(self, extractor: RustExtractor) -> None:
        content = "pub mod routes;"
        result = extractor.extract_imports(content)
        # mod declaration is an import; pub mod is also an export
        assert any(i.source == "routes" for i in result)

    def test_grouped_with_alias(self, extractor: RustExtractor) -> None:
        content = "use std::collections::{HashMap, BTreeMap as BMap};"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert "HashMap" in result[0].symbols
        assert "BTreeMap" in result[0].symbols

    def test_multiple_use_statements(self, extractor: RustExtractor) -> None:
        content = """
use std::io;
use serde::Deserialize;
use crate::models::User;
"""
        result = extractor.extract_imports(content)
        assert len(result) == 3

    def test_no_duplicates(self, extractor: RustExtractor) -> None:
        content = """
use std::io;
use std::io;
"""
        result = extractor.extract_imports(content)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


class TestExtractExports:
    """Tests for RustExtractor.extract_exports()."""

    def test_pub_fn(self, extractor: RustExtractor) -> None:
        content = "pub fn handle_request() {}"
        result = extractor.extract_exports(content)
        assert any(e.name == "handle_request" and e.kind == "function" for e in result)

    def test_pub_async_fn(self, extractor: RustExtractor) -> None:
        content = "pub async fn fetch_data() {}"
        result = extractor.extract_exports(content)
        assert any(e.name == "fetch_data" and e.kind == "function" for e in result)

    def test_pub_crate_fn(self, extractor: RustExtractor) -> None:
        content = "pub(crate) fn internal_helper() {}"
        result = extractor.extract_exports(content)
        assert any(e.name == "internal_helper" and e.kind == "function" for e in result)

    def test_pub_struct(self, extractor: RustExtractor) -> None:
        content = "pub struct Server {}"
        result = extractor.extract_exports(content)
        assert any(e.name == "Server" and e.kind == "type" for e in result)

    def test_pub_enum(self, extractor: RustExtractor) -> None:
        content = "pub enum Status { Active, Inactive }"
        result = extractor.extract_exports(content)
        assert any(e.name == "Status" and e.kind == "type" for e in result)

    def test_pub_trait(self, extractor: RustExtractor) -> None:
        content = "pub trait Handler {}"
        result = extractor.extract_exports(content)
        assert any(e.name == "Handler" and e.kind == "type" for e in result)

    def test_pub_type(self, extractor: RustExtractor) -> None:
        content = "pub type Result<T> = std::result::Result<T, Error>;"
        result = extractor.extract_exports(content)
        assert any(e.name == "Result" and e.kind == "type" for e in result)

    def test_pub_const(self, extractor: RustExtractor) -> None:
        content = "pub const MAX_SIZE: usize = 1024;"
        result = extractor.extract_exports(content)
        assert any(e.name == "MAX_SIZE" and e.kind == "variable" for e in result)

    def test_pub_static(self, extractor: RustExtractor) -> None:
        content = "pub static GLOBAL: Mutex<Vec<u8>> = Mutex::new(Vec::new());"
        result = extractor.extract_exports(content)
        assert any(e.name == "GLOBAL" and e.kind == "variable" for e in result)

    def test_pub_mod(self, extractor: RustExtractor) -> None:
        content = "pub mod routes {}"
        # pub mod is an export (as variable in ghagga convention)
        result = extractor.extract_exports(content)
        assert any(e.name == "routes" for e in result)

    def test_non_pub_excluded(self, extractor: RustExtractor) -> None:
        content = """
fn private_fn() {}
struct PrivateStruct {}
enum PrivateEnum {}
"""
        result = extractor.extract_exports(content)
        assert len(result) == 0

    def test_multiple_exports(self, extractor: RustExtractor) -> None:
        content = """
pub fn handler() {}
pub struct Server {}
pub enum Status {}
pub trait Service {}
pub const MAX: usize = 10;
"""
        result = extractor.extract_exports(content)
        names = {e.name for e in result}
        assert names == {"handler", "Server", "Status", "Service", "MAX"}


# ---------------------------------------------------------------------------
# Test file detection
# ---------------------------------------------------------------------------


class TestDetectTestFile:
    """Tests for RustExtractor.detect_test_file()."""

    @pytest.mark.parametrize(
        "path",
        [
            "src/handler_test.rs",
            "tests/integration_test.rs",
        ],
    )
    def test_is_test_file_by_name(self, extractor: RustExtractor, path: str) -> None:
        assert extractor.detect_test_file(path) is True

    def test_is_test_file_by_cfg(self, extractor: RustExtractor) -> None:
        assert extractor.detect_test_file(
            "src/handler.rs",
            content="#[cfg(test)]\nmod tests {}",
        ) is True

    @pytest.mark.parametrize(
        "path",
        [
            "src/handler.rs",
            "src/lib.rs",
            "src/main.rs",
        ],
    )
    def test_not_test_file(self, extractor: RustExtractor, path: str) -> None:
        assert extractor.detect_test_file(path) is False
