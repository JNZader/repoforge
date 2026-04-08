"""Tests for repoforge.search.prepare."""

from repoforge.graph import Node
from repoforge.ir.repo import ModuleInfo
from repoforge.search.prepare import (
    module_to_text,
    node_to_text,
    prepare_all,
    symbol_to_text,
)
from repoforge.symbols.extractor import Symbol


class TestSymbolToText:
    def test_function_with_params(self):
        sym = Symbol(
            name="authenticate",
            kind="function",
            file="src/auth.py",
            line=10,
            end_line=25,
            params=["token: str", "secret: str"],
        )
        text = symbol_to_text(sym)
        assert "function authenticate" in text
        assert "src/auth.py" in text
        assert "token: str" in text
        assert "secret: str" in text

    def test_class_no_params(self):
        sym = Symbol(
            name="UserService",
            kind="class",
            file="src/service.py",
            line=1,
            end_line=50,
        )
        text = symbol_to_text(sym)
        assert "class UserService" in text
        assert "src/service.py" in text
        assert "params" not in text


class TestModuleToText:
    def test_full_module(self):
        mod = ModuleInfo(
            path="src/auth.py",
            name="auth",
            language="python",
            exports=["authenticate", "login"],
            imports=["jwt", "hashlib"],
            summary_hint="Authentication utilities",
        )
        text = module_to_text(mod)
        assert "module auth" in text
        assert "src/auth.py" in text
        assert "python" in text
        assert "authenticate" in text
        assert "jwt" in text

    def test_minimal_module(self):
        mod = ModuleInfo(path="src/empty.py", name="empty", language="python")
        text = module_to_text(mod)
        assert "module empty" in text
        assert "src/empty.py" in text


class TestNodeToText:
    def test_module_node(self):
        node = Node(
            id="src/auth.py",
            name="auth",
            node_type="module",
            layer="backend",
            file_path="src/auth.py",
            exports=["authenticate", "login"],
        )
        text = node_to_text(node)
        assert "module auth" in text
        assert "backend" in text
        assert "src/auth.py" in text
        assert "authenticate" in text

    def test_layer_node(self):
        node = Node(
            id="layer:backend",
            name="backend",
            node_type="layer",
            layer="backend",
        )
        text = node_to_text(node)
        assert "layer backend" in text


class TestPrepareAll:
    def test_combines_all_entity_types(self):
        sym = Symbol(
            name="foo", kind="function", file="a.py",
            line=1, end_line=5, params=["x"],
        )
        mod = ModuleInfo(path="b.py", name="b", language="python")
        node = Node(id="c.py", name="c", node_type="module")

        results = prepare_all(symbols=[sym], modules=[mod], nodes=[node])
        assert len(results) == 3

        ids = [r[0] for r in results]
        types = [r[1] for r in results]
        assert "a.py::foo" in ids
        assert "b.py" in ids
        assert "c.py" in ids
        assert types == ["symbol", "module", "node"]

    def test_empty_inputs(self):
        assert prepare_all() == []
        assert prepare_all(symbols=[], modules=[], nodes=[]) == []

    def test_partial_inputs(self):
        sym = Symbol(
            name="bar", kind="function", file="x.py",
            line=1, end_line=3,
        )
        results = prepare_all(symbols=[sym])
        assert len(results) == 1
        assert results[0][1] == "symbol"
