"""
tests/test_extractors/test_go.py — Tests for GoExtractor.

Tests cover:
- Single imports: import "fmt"
- Block imports: import ( "fmt"\n "os" )
- Aliased imports: import m "math"
- Dot imports: import . "strings"
- Exported functions (uppercase), including methods with receivers
- Exported types (struct, interface)
- Exported vars/consts
- Non-exported (lowercase) identifiers excluded
- Test file detection
"""

import pytest

from repoforge.extractors.go import GoExtractor


@pytest.fixture
def extractor() -> GoExtractor:
    return GoExtractor()


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------


class TestExtractImports:
    """Tests for GoExtractor.extract_imports()."""

    def test_single_import(self, extractor: GoExtractor) -> None:
        content = 'import "fmt"'
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "fmt"
        assert result[0].symbols == []

    def test_block_import(self, extractor: GoExtractor) -> None:
        content = '''import (
    "fmt"
    "os"
    "net/http"
)'''
        result = extractor.extract_imports(content)
        assert len(result) == 3
        sources = {i.source for i in result}
        assert sources == {"fmt", "os", "net/http"}

    def test_aliased_import(self, extractor: GoExtractor) -> None:
        content = 'import m "math"'
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "math"
        assert result[0].symbols == ["m"]

    def test_dot_import(self, extractor: GoExtractor) -> None:
        content = 'import . "strings"'
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "strings"
        assert result[0].symbols == ["."]

    def test_aliased_in_block(self, extractor: GoExtractor) -> None:
        content = '''import (
    "fmt"
    mux "github.com/gorilla/mux"
)'''
        result = extractor.extract_imports(content)
        assert len(result) == 2
        mux_imp = next(i for i in result if i.source == "github.com/gorilla/mux")
        assert mux_imp.symbols == ["mux"]

    def test_external_import(self, extractor: GoExtractor) -> None:
        content = 'import "github.com/gin-gonic/gin"'
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "github.com/gin-gonic/gin"
        # External packages have dots, so not relative
        assert result[0].is_relative is False

    def test_stdlib_not_relative(self, extractor: GoExtractor) -> None:
        content = 'import "fmt"'
        result = extractor.extract_imports(content)
        assert result[0].is_relative is False

    def test_no_duplicate_imports(self, extractor: GoExtractor) -> None:
        content = '''import "fmt"
import (
    "fmt"
    "os"
)'''
        result = extractor.extract_imports(content)
        sources = [i.source for i in result]
        assert sources.count("fmt") == 1

    def test_mixed_stdlib_and_external(self, extractor: GoExtractor) -> None:
        content = '''import (
    "context"
    "fmt"
    "github.com/stretchr/testify/assert"
    "myproject/internal/handler"
)'''
        result = extractor.extract_imports(content)
        assert len(result) == 4
        ext = next(i for i in result if "testify" in i.source)
        assert ext.is_relative is False


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


class TestExtractExports:
    """Tests for GoExtractor.extract_exports()."""

    def test_exported_function(self, extractor: GoExtractor) -> None:
        content = "func HandleRequest(w http.ResponseWriter, r *http.Request) {}"
        result = extractor.extract_exports(content)
        assert len(result) == 1
        assert result[0].name == "HandleRequest"
        assert result[0].kind == "function"

    def test_unexported_function_excluded(self, extractor: GoExtractor) -> None:
        content = "func handleRequest(w http.ResponseWriter, r *http.Request) {}"
        result = extractor.extract_exports(content)
        assert len(result) == 0

    def test_method_with_receiver(self, extractor: GoExtractor) -> None:
        content = "func (s *Server) Start() error {}"
        result = extractor.extract_exports(content)
        assert len(result) == 1
        assert result[0].name == "Start"
        assert result[0].kind == "function"

    def test_unexported_method_excluded(self, extractor: GoExtractor) -> None:
        content = "func (s *Server) start() error {}"
        result = extractor.extract_exports(content)
        assert len(result) == 0

    def test_exported_struct(self, extractor: GoExtractor) -> None:
        content = "type Server struct {}"
        result = extractor.extract_exports(content)
        assert len(result) == 1
        assert result[0].name == "Server"
        assert result[0].kind == "type"

    def test_exported_interface(self, extractor: GoExtractor) -> None:
        content = "type Handler interface {}"
        result = extractor.extract_exports(content)
        assert len(result) == 1
        assert result[0].name == "Handler"
        assert result[0].kind == "type"

    def test_unexported_type_excluded(self, extractor: GoExtractor) -> None:
        content = "type server struct {}"
        result = extractor.extract_exports(content)
        assert len(result) == 0

    def test_exported_var(self, extractor: GoExtractor) -> None:
        content = "var ErrNotFound = errors.New(\"not found\")"
        result = extractor.extract_exports(content)
        assert len(result) == 1
        assert result[0].name == "ErrNotFound"
        assert result[0].kind == "variable"

    def test_exported_const(self, extractor: GoExtractor) -> None:
        content = "const MaxRetries = 3"
        result = extractor.extract_exports(content)
        assert len(result) == 1
        assert result[0].name == "MaxRetries"
        assert result[0].kind == "variable"

    def test_unexported_var_excluded(self, extractor: GoExtractor) -> None:
        content = "var errInternal = errors.New(\"internal\")"
        result = extractor.extract_exports(content)
        assert len(result) == 0

    def test_multiple_exports(self, extractor: GoExtractor) -> None:
        content = """
func HandleRequest(w http.ResponseWriter, r *http.Request) {}
type Server struct {}
var ErrNotFound = errors.New("not found")
const MaxRetries = 3
func helper() {}
"""
        result = extractor.extract_exports(content)
        names = {e.name for e in result}
        assert names == {"HandleRequest", "Server", "ErrNotFound", "MaxRetries"}
        assert "helper" not in names


# ---------------------------------------------------------------------------
# Test file detection
# ---------------------------------------------------------------------------


class TestDetectTestFile:
    """Tests for GoExtractor.detect_test_file()."""

    @pytest.mark.parametrize(
        "path",
        [
            "handler_test.go",
            "internal/server_test.go",
            "pkg/utils_test.go",
        ],
    )
    def test_is_test_file(self, extractor: GoExtractor, path: str) -> None:
        assert extractor.detect_test_file(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "handler.go",
            "internal/server.go",
            "testdata/fixture.go",
        ],
    )
    def test_not_test_file(self, extractor: GoExtractor, path: str) -> None:
        assert extractor.detect_test_file(path) is False
