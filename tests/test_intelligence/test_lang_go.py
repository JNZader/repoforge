"""Tests for Go AST extractor — tree-sitter based."""

import pytest
from pathlib import Path

from repoforge.intelligence.lang_go import GoASTExtractor


@pytest.fixture
def extractor():
    return GoASTExtractor()


class TestGoSymbols:
    """Go symbol extraction."""

    def test_function(self, extractor):
        code = 'package main\n\nfunc New(s *Store, port int) *Server { return nil }'
        symbols = extractor.extract_symbols(code, "server.go")

        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "New"
        assert funcs[0].params == ["s *Store", "port int"]
        assert funcs[0].return_type == "*Server"
        assert "func New(s *Store, port int) *Server" in funcs[0].signature

    def test_method_with_receiver(self, extractor):
        code = 'package main\n\nfunc (s *Server) Start() error { return nil }'
        symbols = extractor.extract_symbols(code, "server.go")

        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 1
        assert methods[0].name == "Start"
        assert methods[0].return_type == "error"
        assert "(s *Server)" in methods[0].signature

    def test_struct_with_fields(self, extractor):
        code = 'package main\n\ntype User struct {\n    Name string\n    Age  int\n}'
        symbols = extractor.extract_symbols(code, "models.go")

        structs = [s for s in symbols if s.kind == "struct"]
        assert len(structs) == 1
        assert structs[0].name == "User"
        assert len(structs[0].fields) == 2
        assert "Name string" in structs[0].fields[0]

    def test_interface(self, extractor):
        code = 'package main\n\ntype Repository interface {\n    Find(id int) *User\n}'
        symbols = extractor.extract_symbols(code, "repo.go")

        ifaces = [s for s in symbols if s.kind == "interface"]
        assert len(ifaces) == 1
        assert ifaces[0].name == "Repository"

    def test_exported_const(self, extractor):
        code = 'package main\n\nconst MaxRetries = 3'
        symbols = extractor.extract_symbols(code, "config.go")

        consts = [s for s in symbols if s.kind == "constant"]
        assert len(consts) == 1
        assert consts[0].name == "MaxRetries"

    def test_unexported_const_excluded(self, extractor):
        code = 'package main\n\nconst maxRetries = 3'
        symbols = extractor.extract_symbols(code, "config.go")
        consts = [s for s in symbols if s.kind == "constant"]
        assert len(consts) == 0

    def test_type_alias(self, extractor):
        code = 'package main\n\ntype ID string'
        symbols = extractor.extract_symbols(code, "types.go")
        types = [s for s in symbols if s.kind == "type"]
        assert len(types) == 1
        assert types[0].name == "ID"

    def test_real_engram_server(self, extractor):
        """Test against real engram server.go if available."""
        server_path = Path("/tmp/engram-test/internal/server/server.go")
        if not server_path.is_file():
            pytest.skip("engram-test fixture not available")

        content = server_path.read_text()
        symbols = extractor.extract_symbols(content, "internal/server/server.go")

        # Should find Server struct, New function, multiple methods
        names = {s.name for s in symbols}
        assert "Server" in names
        assert "New" in names
        assert "Start" in names
        assert len(symbols) >= 10


class TestGoEndpoints:
    """Go endpoint extraction."""

    def test_handlefunc_with_method(self, extractor):
        code = '''package main
func routes() {
    mux.HandleFunc("GET /health", handleHealth)
    mux.HandleFunc("POST /users", handleCreateUser)
}'''
        endpoints = extractor.extract_endpoints(code, "routes.go")
        assert len(endpoints) == 2
        assert endpoints[0].value == "GET /health"
        assert endpoints[1].value == "POST /users"

    def test_handlefunc_without_method(self, extractor):
        code = '''package main
func routes() {
    http.HandleFunc("/api", handler)
}'''
        endpoints = extractor.extract_endpoints(code, "routes.go")
        assert len(endpoints) == 1
        assert "ANY /api" == endpoints[0].value

    def test_echo_style_routes(self, extractor):
        code = '''package main
func routes() {
    e.GET("/users", listUsers)
    e.POST("/users", createUser)
}'''
        endpoints = extractor.extract_endpoints(code, "routes.go")
        assert len(endpoints) == 2
        values = {ep.value for ep in endpoints}
        assert "GET /users" in values
        assert "POST /users" in values

    def test_real_engram_endpoints(self, extractor):
        """Real endpoints from engram server."""
        server_path = Path("/tmp/engram-test/internal/server/server.go")
        if not server_path.is_file():
            pytest.skip("engram-test fixture not available")

        content = server_path.read_text()
        endpoints = extractor.extract_endpoints(content, "server.go")
        values = {ep.value for ep in endpoints}

        assert "GET /health" in values
        assert "POST /sessions" in values
        assert "GET /search" in values
        assert len(endpoints) >= 15


class TestGoSchemas:
    """Go SQL schema extraction."""

    def test_create_table(self, extractor):
        code = '''package store
var schema = `
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE sessions (
    id TEXT PRIMARY KEY
);
`'''
        schemas = extractor.extract_schemas(code, "store.go")
        assert len(schemas) == 2
        names = {s.name for s in schemas}
        assert "users" in names
        assert "sessions" in names

    def test_no_schemas(self, extractor):
        code = 'package main\nfunc main() {}'
        schemas = extractor.extract_schemas(code, "main.go")
        assert len(schemas) == 0

    def test_real_engram_schemas(self, extractor):
        """Real schemas from engram store.go."""
        store_path = Path("/tmp/engram-test/internal/store/store.go")
        if not store_path.is_file():
            pytest.skip("engram-test fixture not available")

        content = store_path.read_text()
        schemas = extractor.extract_schemas(content, "store.go")
        # Engram has CREATE TABLE statements in its schema
        if len(schemas) > 0:
            assert all(s.kind == "schema" for s in schemas)
