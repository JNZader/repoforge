"""Tests for C AST extractor — tree-sitter based."""

import pytest

from repoforge.intelligence.lang_c import CASTExtractor


@pytest.fixture
def extractor():
    return CASTExtractor()


class TestCSymbols:
    """C symbol extraction."""

    def test_function(self, extractor):
        code = "int add(int a, int b) { return a + b; }"
        symbols = extractor.extract_symbols(code, "math.c")

        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "add"
        assert "int" in funcs[0].signature
        assert len(funcs[0].params) == 2

    def test_struct(self, extractor):
        code = "struct Point {\n    int x;\n    int y;\n};"
        symbols = extractor.extract_symbols(code, "geometry.c")

        structs = [s for s in symbols if s.kind == "struct"]
        assert len(structs) == 1
        assert structs[0].name == "Point"
        assert len(structs[0].fields) == 2

    def test_enum(self, extractor):
        code = "enum Color { RED, GREEN, BLUE };"
        symbols = extractor.extract_symbols(code, "types.c")

        enums = [s for s in symbols if s.kind == "type"]
        assert len(enums) == 1
        assert enums[0].name == "Color"
        assert len(enums[0].fields) == 3

    def test_macro_constant(self, extractor):
        code = "#define MAX_SIZE 1024"
        symbols = extractor.extract_symbols(code, "config.h")

        consts = [s for s in symbols if s.kind == "constant"]
        assert len(consts) == 1
        assert consts[0].name == "MAX_SIZE"

    def test_function_with_void_return(self, extractor):
        code = "void process(char *data) { }"
        symbols = extractor.extract_symbols(code, "utils.c")

        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "process"
        assert funcs[0].return_type == "void"

    def test_empty_file(self, extractor):
        assert extractor.extract_symbols("", "empty.c") == []

    def test_endpoints_always_empty(self, extractor):
        code = "int main() { return 0; }"
        assert extractor.extract_endpoints(code, "main.c") == []

    def test_schemas_empty(self, extractor):
        code = "int main() { return 0; }"
        assert extractor.extract_schemas(code, "main.c") == []


class TestCSchemas:
    """C schema extraction — SQL in string literals."""

    def test_create_table_in_string(self, extractor):
        code = '''const char *sql = "CREATE TABLE users (id INT, name TEXT)";'''
        schemas = extractor.extract_schemas(code, "db.c")

        assert len(schemas) == 1
        assert schemas[0].name == "users"
        assert schemas[0].kind == "schema"
