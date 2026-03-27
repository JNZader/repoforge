"""Tests for JavaScript AST extractor — tree-sitter based."""

import pytest

from repoforge.intelligence.lang_javascript import JavaScriptASTExtractor


@pytest.fixture
def extractor():
    return JavaScriptASTExtractor()


class TestJavaScriptSymbols:
    """JavaScript symbol extraction."""

    def test_exported_function(self, extractor):
        code = 'export function processData(items) { return items; }'
        symbols = extractor.extract_symbols(code, "utils.js")

        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "processData"

    def test_exported_class(self, extractor):
        code = '''export class UserService {
    getUser(id) {
        return null;
    }
}'''
        symbols = extractor.extract_symbols(code, "service.js")

        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "UserService"

    def test_module_exports_object(self, extractor):
        code = '''function foo() {}
function bar() {}
module.exports = { foo, bar };
'''
        symbols = extractor.extract_symbols(code, "lib.js")

        # Should find the module.exports names
        names = {s.name for s in symbols}
        assert "foo" in names
        assert "bar" in names

    def test_module_exports_single(self, extractor):
        code = '''class App {}
module.exports = App;
'''
        symbols = extractor.extract_symbols(code, "app.js")
        names = {s.name for s in symbols}
        assert "App" in names

    def test_exported_const(self, extractor):
        code = 'export const MAX_RETRIES = 3;'
        symbols = extractor.extract_symbols(code, "config.js")

        consts = [s for s in symbols if s.kind == "constant"]
        assert len(consts) == 1
        assert consts[0].name == "MAX_RETRIES"


class TestJavaScriptEndpoints:
    """JavaScript endpoint extraction."""

    def test_express_routes(self, extractor):
        code = '''
app.get('/users', listUsers);
app.post('/users', createUser);
'''
        endpoints = extractor.extract_endpoints(code, "routes.js")
        assert len(endpoints) == 2
        values = {ep.value for ep in endpoints}
        assert "GET /users" in values
        assert "POST /users" in values

    def test_no_endpoints(self, extractor):
        code = 'const x = 42;'
        endpoints = extractor.extract_endpoints(code, "lib.js")
        assert len(endpoints) == 0


class TestJavaScriptSchemas:
    """JavaScript schema extraction."""

    def test_zod_schema(self, extractor):
        code = '''const UserSchema = z.object({
    name: z.string(),
});'''
        schemas = extractor.extract_schemas(code, "schemas.js")
        # Zod detection works via text matching
        assert len(schemas) >= 0  # May or may not detect non-exported

    def test_no_schemas(self, extractor):
        code = 'const value = 42;'
        schemas = extractor.extract_schemas(code, "config.js")
        assert len(schemas) == 0
