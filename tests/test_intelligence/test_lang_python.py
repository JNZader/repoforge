"""Tests for Python AST extractor — tree-sitter based."""

import pytest

from repoforge.intelligence.lang_python import PythonASTExtractor


@pytest.fixture
def extractor():
    return PythonASTExtractor()


class TestPythonSymbols:
    """Python symbol extraction."""

    def test_function_with_type_hints(self, extractor):
        code = 'def process(data: list[str], limit: int = 10) -> dict:\n    return {}'
        symbols = extractor.extract_symbols(code, "utils.py")

        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "process"
        assert funcs[0].return_type == "dict"
        assert any("data" in p for p in funcs[0].params)

    def test_async_function(self, extractor):
        code = 'async def fetch(url: str) -> bytes:\n    pass'
        symbols = extractor.extract_symbols(code, "client.py")

        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert "async def" in funcs[0].signature
        assert funcs[0].return_type == "bytes"

    def test_class_with_bases(self, extractor):
        code = '''class User(BaseModel):
    """A user model."""
    name: str
    age: int
'''
        symbols = extractor.extract_symbols(code, "models.py")

        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "User"
        assert "BaseModel" in classes[0].signature
        assert classes[0].docstring is not None

    def test_class_methods(self, extractor):
        code = '''class Service:
    def get(self, id: int) -> dict:
        pass
    async def update(self, data: dict) -> None:
        pass
'''
        symbols = extractor.extract_symbols(code, "service.py")

        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 2
        names = {m.name for m in methods}
        assert "get" in names
        assert "update" in names

    def test_decorated_function(self, extractor):
        code = '''@cache
@validate
def compute(x: int) -> int:
    return x * 2
'''
        symbols = extractor.extract_symbols(code, "math.py")

        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert len(funcs[0].decorators) == 2

    def test_docstring_extraction(self, extractor):
        code = '''def foo():
    """This is the docstring."""
    pass
'''
        symbols = extractor.extract_symbols(code, "foo.py")
        assert len(symbols) >= 1
        assert symbols[0].docstring == "This is the docstring."


class TestPythonEndpoints:
    """Python endpoint extraction."""

    def test_flask_route(self, extractor):
        code = '''@app.route("/users")
def get_users():
    pass
'''
        endpoints = extractor.extract_endpoints(code, "views.py")
        assert len(endpoints) == 1
        assert endpoints[0].value == "ANY /users"

    def test_fastapi_get(self, extractor):
        code = '''@router.get("/items/{id}")
async def get_item(id: int):
    pass
'''
        endpoints = extractor.extract_endpoints(code, "routes.py")
        assert len(endpoints) == 1
        assert "GET" in endpoints[0].value
        assert "/items/{id}" in endpoints[0].value

    def test_multiple_endpoints(self, extractor):
        code = '''@app.get("/users")
def list_users(): pass

@app.post("/users")
def create_user(): pass

@app.delete("/users/{id}")
def delete_user(): pass
'''
        endpoints = extractor.extract_endpoints(code, "api.py")
        assert len(endpoints) == 3

    def test_no_endpoints(self, extractor):
        code = 'def regular_function():\n    pass'
        endpoints = extractor.extract_endpoints(code, "utils.py")
        assert len(endpoints) == 0


class TestPythonSchemas:
    """Python schema extraction."""

    def test_pydantic_model(self, extractor):
        code = '''class User(BaseModel):
    name: str
    age: int
'''
        schemas = extractor.extract_schemas(code, "schemas.py")
        assert len(schemas) == 1
        assert schemas[0].name == "User"
        assert schemas[0].kind == "schema"

    def test_sqlmodel(self, extractor):
        code = '''class Hero(SQLModel, table=True):
    id: int | None
    name: str
'''
        schemas = extractor.extract_schemas(code, "models.py")
        assert len(schemas) == 1
        assert schemas[0].name == "Hero"

    def test_non_schema_class_excluded(self, extractor):
        code = '''class RegularClass:
    pass
'''
        schemas = extractor.extract_schemas(code, "lib.py")
        assert len(schemas) == 0
