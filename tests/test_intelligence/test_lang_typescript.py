"""Tests for TypeScript AST extractor — tree-sitter based."""

import pytest

from repoforge.intelligence.lang_typescript import TypeScriptASTExtractor


@pytest.fixture
def extractor():
    return TypeScriptASTExtractor()


class TestTypeScriptSymbols:
    """TypeScript symbol extraction."""

    def test_exported_function(self, extractor):
        code = 'export function processData(items: string[], limit: number): Record<string, any> { return {}; }'
        symbols = extractor.extract_symbols(code, "utils.ts")

        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "processData"
        assert any("items" in p for p in funcs[0].params)

    def test_exported_class(self, extractor):
        code = '''export class UserService {
    async getUser(id: string): Promise<User> {
        return {} as User;
    }
}'''
        symbols = extractor.extract_symbols(code, "service.ts")

        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "UserService"

    def test_interface(self, extractor):
        code = '''export interface User {
    name: string;
    age: number;
}'''
        symbols = extractor.extract_symbols(code, "types.ts")

        ifaces = [s for s in symbols if s.kind == "interface"]
        assert len(ifaces) == 1
        assert ifaces[0].name == "User"
        assert len(ifaces[0].fields) == 2

    def test_type_alias(self, extractor):
        code = 'export type Config = { port: number; host: string; };'
        symbols = extractor.extract_symbols(code, "config.ts")

        types = [s for s in symbols if s.kind == "type"]
        assert len(types) == 1
        assert types[0].name == "Config"

    def test_exported_const(self, extractor):
        code = 'export const MAX_RETRIES = 3;'
        symbols = extractor.extract_symbols(code, "config.ts")

        consts = [s for s in symbols if s.kind == "constant"]
        assert len(consts) == 1
        assert consts[0].name == "MAX_RETRIES"

    def test_async_function(self, extractor):
        code = 'export async function fetchData(url: string): Promise<Response> { return fetch(url); }'
        symbols = extractor.extract_symbols(code, "api.ts")

        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert "async" in funcs[0].signature


class TestTypeScriptEndpoints:
    """TypeScript endpoint extraction."""

    def test_express_routes(self, extractor):
        code = '''
router.get('/users/:id', getUser);
app.post('/api/login', handleLogin);
'''
        endpoints = extractor.extract_endpoints(code, "routes.ts")
        assert len(endpoints) == 2
        values = {ep.value for ep in endpoints}
        assert "GET /users/:id" in values
        assert "POST /api/login" in values

    def test_no_endpoints(self, extractor):
        code = 'const x = 42;'
        endpoints = extractor.extract_endpoints(code, "lib.ts")
        assert len(endpoints) == 0


class TestTypeScriptSchemas:
    """TypeScript schema extraction."""

    def test_zod_schema(self, extractor):
        code = '''export const UserSchema = z.object({
    name: z.string(),
    age: z.number(),
});'''
        schemas = extractor.extract_schemas(code, "schemas.ts")
        assert len(schemas) >= 1
        assert any(s.name == "UserSchema" for s in schemas)

    def test_no_schemas(self, extractor):
        code = 'export const value = 42;'
        schemas = extractor.extract_schemas(code, "config.ts")
        assert len(schemas) == 0
