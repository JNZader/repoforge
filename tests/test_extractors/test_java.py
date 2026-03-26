"""
tests/test_extractors/test_java.py — Tests for JavaExtractor.

Tests cover:
- Regular imports (import x.y.z)
- Static imports (import static x.y.z)
- Wildcard imports (import x.y.*)
- Public classes, abstract classes
- Public interfaces, enums, records
- Public methods (excluding Java boilerplate)
- Test file detection
"""

import pytest

from repoforge.extractors.java import JavaExtractor


@pytest.fixture
def extractor() -> JavaExtractor:
    return JavaExtractor()


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------


class TestExtractImports:
    """Tests for JavaExtractor.extract_imports()."""

    def test_regular_import(self, extractor: JavaExtractor) -> None:
        content = "import java.util.List;"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "java.util.List"
        assert result[0].symbols == ["List"]

    def test_static_import(self, extractor: JavaExtractor) -> None:
        content = "import static org.junit.Assert.assertEquals;"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "org.junit.Assert.assertEquals"
        assert result[0].symbols == ["assertEquals"]

    def test_wildcard_import(self, extractor: JavaExtractor) -> None:
        content = "import java.util.*;"
        result = extractor.extract_imports(content)
        assert len(result) == 1
        assert result[0].source == "java.util.*"
        assert result[0].symbols == []

    def test_multiple_imports(self, extractor: JavaExtractor) -> None:
        content = """
import java.util.List;
import java.util.Map;
import java.io.IOException;
"""
        result = extractor.extract_imports(content)
        assert len(result) == 3
        sources = {i.source for i in result}
        assert sources == {"java.util.List", "java.util.Map", "java.io.IOException"}

    def test_no_duplicates(self, extractor: JavaExtractor) -> None:
        content = """
import java.util.List;
import java.util.List;
"""
        result = extractor.extract_imports(content)
        assert len(result) == 1

    def test_not_relative(self, extractor: JavaExtractor) -> None:
        content = "import com.example.MyClass;"
        result = extractor.extract_imports(content)
        assert result[0].is_relative is False


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


class TestExtractExports:
    """Tests for JavaExtractor.extract_exports()."""

    def test_public_class(self, extractor: JavaExtractor) -> None:
        content = "public class UserService {}"
        result = extractor.extract_exports(content)
        assert any(e.name == "UserService" and e.kind == "class" for e in result)

    def test_public_abstract_class(self, extractor: JavaExtractor) -> None:
        content = "public abstract class BaseHandler {}"
        result = extractor.extract_exports(content)
        assert any(e.name == "BaseHandler" and e.kind == "class" for e in result)

    def test_public_interface(self, extractor: JavaExtractor) -> None:
        content = "public interface Repository {}"
        result = extractor.extract_exports(content)
        assert any(e.name == "Repository" and e.kind == "type" for e in result)

    def test_public_enum(self, extractor: JavaExtractor) -> None:
        content = "public enum Status { ACTIVE, INACTIVE }"
        result = extractor.extract_exports(content)
        assert any(e.name == "Status" and e.kind == "type" for e in result)

    def test_public_record(self, extractor: JavaExtractor) -> None:
        content = "public record Point(int x, int y) {}"
        result = extractor.extract_exports(content)
        assert any(e.name == "Point" and e.kind == "type" for e in result)

    def test_public_method(self, extractor: JavaExtractor) -> None:
        content = "public void handleRequest(Request req) {}"
        result = extractor.extract_exports(content)
        assert any(e.name == "handleRequest" and e.kind == "function" for e in result)

    def test_boilerplate_excluded(self, extractor: JavaExtractor) -> None:
        content = """
public String toString() { return ""; }
public int hashCode() { return 0; }
public boolean equals(Object o) { return false; }
"""
        result = extractor.extract_exports(content)
        names = {e.name for e in result}
        assert "toString" not in names
        assert "hashCode" not in names
        assert "equals" not in names

    def test_static_method(self, extractor: JavaExtractor) -> None:
        content = "public static void init() {}"
        result = extractor.extract_exports(content)
        assert any(e.name == "init" and e.kind == "function" for e in result)

    def test_multiple_exports(self, extractor: JavaExtractor) -> None:
        content = """
public class UserService {
    public void createUser(User user) {}
    public User getUser(String id) { return null; }
}
"""
        result = extractor.extract_exports(content)
        names = {e.name for e in result}
        assert "UserService" in names
        assert "createUser" in names
        assert "getUser" in names


# ---------------------------------------------------------------------------
# Test file detection
# ---------------------------------------------------------------------------


class TestDetectTestFile:
    """Tests for JavaExtractor.detect_test_file()."""

    @pytest.mark.parametrize(
        "path",
        [
            "src/test/java/UserServiceTest.java",
            "src/test/java/UserServiceTests.java",
            "src/test/java/UserServiceIT.java",
        ],
    )
    def test_is_test_file(self, extractor: JavaExtractor, path: str) -> None:
        assert extractor.detect_test_file(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "src/main/java/UserService.java",
            "src/main/java/TestHelper.java",
        ],
    )
    def test_not_test_file(self, extractor: JavaExtractor, path: str) -> None:
        assert extractor.detect_test_file(path) is False
