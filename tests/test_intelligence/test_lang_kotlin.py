"""Tests for Kotlin AST extractor — tree-sitter based."""

import pytest

from repoforge.intelligence.lang_kotlin import KotlinASTExtractor


@pytest.fixture
def extractor():
    return KotlinASTExtractor()


class TestKotlinSymbols:
    """Kotlin symbol extraction."""

    def test_function(self, extractor):
        code = 'fun greet(name: String): String { return "Hello $name" }'
        symbols = extractor.extract_symbols(code, "main.kt")

        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "greet"
        assert "fun greet" in funcs[0].signature

    def test_class(self, extractor):
        code = "class UserService {\n    fun findById(id: Int): User? { return null }\n}"
        symbols = extractor.extract_symbols(code, "service.kt")

        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "UserService"

        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 1
        assert methods[0].name == "findById"

    def test_data_class(self, extractor):
        code = "data class User(val name: String, val age: Int)"
        symbols = extractor.extract_symbols(code, "models.kt")

        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "User"
        assert "data class" in classes[0].signature

    def test_interface(self, extractor):
        code = "interface Repository {\n    fun findAll(): List<Item>\n}"
        symbols = extractor.extract_symbols(code, "repo.kt")

        ifaces = [s for s in symbols if s.kind == "interface"]
        assert len(ifaces) == 1
        assert ifaces[0].name == "Repository"

    def test_object_declaration(self, extractor):
        code = "object Singleton {\n    fun getInstance(): Singleton = this\n}"
        symbols = extractor.extract_symbols(code, "singleton.kt")

        objects = [s for s in symbols if s.kind == "class" and s.name == "Singleton"]
        assert len(objects) == 1
        assert "object Singleton" in objects[0].signature

    def test_empty_file(self, extractor):
        assert extractor.extract_symbols("", "empty.kt") == []

    def test_endpoints_empty(self, extractor):
        code = "fun main() { println(\"Hello\") }"
        assert extractor.extract_endpoints(code, "main.kt") == []

    def test_schemas_empty(self, extractor):
        code = "class Plain { }"
        assert extractor.extract_schemas(code, "plain.kt") == []


class TestKotlinEndpoints:
    """Kotlin endpoint extraction — Spring/Ktor."""

    def test_ktor_route(self, extractor):
        code = '''fun Application.configureRouting() {
    routing {
        get("/users") { call.respond("ok") }
    }
}'''
        endpoints = extractor.extract_endpoints(code, "routes.kt")
        assert any("GET /users" in e.value for e in endpoints)
