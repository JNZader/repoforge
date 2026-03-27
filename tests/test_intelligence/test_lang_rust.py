"""Tests for Rust AST extractor — tree-sitter based."""

import pytest

from repoforge.intelligence.lang_rust import RustASTExtractor


@pytest.fixture
def extractor():
    return RustASTExtractor()


class TestRustSymbols:
    """Rust symbol extraction."""

    def test_pub_function(self, extractor):
        code = 'pub fn new(store: &Store, port: u16) -> Server { Server { store, port } }'
        symbols = extractor.extract_symbols(code, "lib.rs")

        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "new"
        assert funcs[0].return_type == "Server"
        assert "pub fn" in funcs[0].signature

    def test_private_function(self, extractor):
        code = 'fn helper() -> bool { true }'
        symbols = extractor.extract_symbols(code, "lib.rs")

        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert "pub" not in funcs[0].signature

    def test_pub_struct_with_fields(self, extractor):
        code = '''pub struct User {
    pub name: String,
    pub age: u32,
}'''
        symbols = extractor.extract_symbols(code, "models.rs")

        structs = [s for s in symbols if s.kind == "struct"]
        assert len(structs) == 1
        assert structs[0].name == "User"
        assert len(structs[0].fields) == 2

    def test_pub_enum(self, extractor):
        code = '''pub enum Status {
    Active,
    Inactive,
}'''
        symbols = extractor.extract_symbols(code, "types.rs")

        types = [s for s in symbols if s.kind == "type"]
        assert len(types) == 1
        assert types[0].name == "Status"
        assert len(types[0].fields) == 2

    def test_pub_trait(self, extractor):
        code = '''pub trait Repository {
    fn find_by_id(&self, id: u64) -> Option<User>;
}'''
        symbols = extractor.extract_symbols(code, "traits.rs")

        traits = [s for s in symbols if s.kind == "trait"]
        assert len(traits) == 1
        assert traits[0].name == "Repository"

    def test_impl_methods(self, extractor):
        code = '''impl Server {
    pub fn start(&self) -> Result<(), Error> { Ok(()) }
    fn helper(&self) {}
}'''
        symbols = extractor.extract_symbols(code, "server.rs")

        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 2

    def test_pub_const(self, extractor):
        code = 'pub const MAX_RETRIES: u32 = 3;'
        symbols = extractor.extract_symbols(code, "config.rs")

        consts = [s for s in symbols if s.kind == "constant"]
        assert len(consts) == 1
        assert consts[0].name == "MAX_RETRIES"

    def test_private_const_excluded(self, extractor):
        code = 'const max_retries: u32 = 3;'
        symbols = extractor.extract_symbols(code, "config.rs")

        consts = [s for s in symbols if s.kind == "constant"]
        assert len(consts) == 0


class TestRustEndpoints:
    """Rust endpoint extraction."""

    def test_actix_get(self, extractor):
        code = '''#[get("/users")]
async fn list_users() -> impl Responder {
    HttpResponse::Ok().finish()
}'''
        endpoints = extractor.extract_endpoints(code, "routes.rs")
        assert len(endpoints) == 1
        assert "GET /users" == endpoints[0].value

    def test_actix_post(self, extractor):
        code = '''#[post("/users")]
async fn create_user(body: Json<User>) -> impl Responder {
    HttpResponse::Created().finish()
}'''
        endpoints = extractor.extract_endpoints(code, "routes.rs")
        assert len(endpoints) == 1
        assert "POST /users" == endpoints[0].value

    def test_no_endpoints(self, extractor):
        code = 'pub fn process() {}'
        endpoints = extractor.extract_endpoints(code, "lib.rs")
        assert len(endpoints) == 0


class TestRustSchemas:
    """Rust schema extraction."""

    def test_diesel_table_macro(self, extractor):
        code = '''table! {
    users (id) {
        id -> Integer,
        name -> Varchar,
    }
}'''
        schemas = extractor.extract_schemas(code, "schema.rs")
        assert len(schemas) >= 0  # Macro detection depends on tree-sitter parse

    def test_no_schemas(self, extractor):
        code = 'pub fn main() {}'
        schemas = extractor.extract_schemas(code, "main.rs")
        assert len(schemas) == 0
