"""Tests for symbol extraction from source code."""

import pytest
from repoforge.symbols.extractor import Symbol, extract_symbols, detect_language


class TestDetectLanguage:

    def test_python(self):
        assert detect_language("src/app.py") == "python"

    def test_typescript(self):
        assert detect_language("src/app.ts") == "typescript"

    def test_tsx(self):
        assert detect_language("src/App.tsx") == "typescript"

    def test_javascript(self):
        assert detect_language("lib/utils.js") == "javascript"

    def test_go(self):
        assert detect_language("cmd/main.go") == "go"

    def test_unsupported(self):
        assert detect_language("Makefile") is None

    def test_rust_unsupported(self):
        assert detect_language("src/main.rs") is None


class TestPythonExtraction:

    def test_simple_function(self):
        code = "def hello(name: str) -> str:\n    return f'Hello {name}'\n"
        symbols = extract_symbols(code, "python", "app.py")
        assert len(symbols) == 1
        sym = symbols[0]
        assert sym.name == "hello"
        assert sym.kind == "function"
        assert sym.file == "app.py"
        assert sym.line == 1
        assert sym.params == ["name: str"]

    def test_class_extraction(self):
        code = "class UserService:\n    def __init__(self):\n        pass\n"
        symbols = extract_symbols(code, "python", "svc.py")
        # class + __init__ method
        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "UserService"

    def test_multiple_functions(self):
        code = (
            "def foo():\n    pass\n\n"
            "def bar(x: int):\n    return x + 1\n\n"
            "def baz(a, b):\n    return a + b\n"
        )
        symbols = extract_symbols(code, "python", "utils.py")
        funcs = [s for s in symbols if s.kind == "function"]
        names = [f.name for f in funcs]
        assert "foo" in names
        assert "bar" in names
        assert "baz" in names

    def test_empty_content(self):
        assert extract_symbols("", "python", "empty.py") == []

    def test_whitespace_only(self):
        assert extract_symbols("   \n\n  ", "python", "blank.py") == []

    def test_symbol_id_property(self):
        code = "def process():\n    pass\n"
        symbols = extract_symbols(code, "python", "worker.py")
        assert symbols[0].id == "worker.py::process"

    def test_nested_function_extraction(self):
        code = (
            "def outer():\n"
            "    def inner():\n"
            "        pass\n"
            "    inner()\n"
        )
        symbols = extract_symbols(code, "python", "nested.py")
        names = [s.name for s in symbols]
        assert "outer" in names
        assert "inner" in names


class TestTypeScriptExtraction:

    def test_function_declaration(self):
        code = "export function processData(items: string[]): void {\n  return;\n}\n"
        symbols = extract_symbols(code, "typescript", "utils.ts")
        assert len(symbols) >= 1
        sym = symbols[0]
        assert sym.name == "processData"
        assert sym.kind == "function"

    def test_arrow_function(self):
        code = "export const handler = (req: Request, res: Response) => {\n  res.send('ok');\n};\n"
        symbols = extract_symbols(code, "typescript", "handler.ts")
        funcs = [s for s in symbols if s.kind == "function"]
        assert any(s.name == "handler" for s in funcs)

    def test_class_declaration(self):
        code = "export class UserController {\n  constructor() {}\n}\n"
        symbols = extract_symbols(code, "typescript", "ctrl.ts")
        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "UserController"

    def test_async_function(self):
        code = "export async function fetchUser(id: number): Promise<User> {\n  return db.get(id);\n}\n"
        symbols = extract_symbols(code, "typescript", "api.ts")
        assert any(s.name == "fetchUser" for s in symbols)


class TestGoExtraction:

    def test_function(self):
        code = "func ProcessItems(items []string) error {\n\treturn nil\n}\n"
        symbols = extract_symbols(code, "go", "main.go")
        assert len(symbols) >= 1
        sym = symbols[0]
        assert sym.name == "ProcessItems"
        assert sym.kind == "function"

    def test_method(self):
        code = "func (s *Server) Start(port int) error {\n\treturn nil\n}\n"
        symbols = extract_symbols(code, "go", "server.go")
        assert any(s.name == "Start" for s in symbols)

    def test_struct_type(self):
        code = "type Config struct {\n\tPort int\n\tHost string\n}\n"
        symbols = extract_symbols(code, "go", "config.go")
        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "Config"


class TestUnsupportedLanguage:

    def test_returns_empty(self):
        assert extract_symbols("fn main() {}", "rust", "main.rs") == []

    def test_unknown_language(self):
        assert extract_symbols("code", "brainfuck", "prog.bf") == []
