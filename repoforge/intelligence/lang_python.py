"""
Python AST Extractor — tree-sitter based analysis for Python source files.

Extracts functions (with type hints), classes (with bases + methods),
decorators, endpoints (@app.route, @router.get), and schemas
(SQLAlchemy models, Pydantic models, Django models).
"""

from __future__ import annotations

import re

from ..facts import FactItem
from .ast_extractor import (
    ASTSymbol,
    find_children,
    find_first_child,
    get_parser,
    node_text,
    parse_source,
)


class PythonASTExtractor:
    """Tree-sitter based extractor for Python files."""

    language_name: str = "python"
    file_extensions: list[str] = [".py"]

    def __init__(self) -> None:
        self._parser = get_parser("python")

    def extract_symbols(self, content: str, file_path: str) -> list[ASTSymbol]:
        root = parse_source(self._parser, content)
        if root is None:
            return []

        symbols: list[ASTSymbol] = []
        self._walk_symbols(root, file_path, symbols)
        return symbols

    def extract_endpoints(self, content: str, file_path: str) -> list[FactItem]:
        root = parse_source(self._parser, content)
        if root is None:
            return []

        endpoints: list[FactItem] = []
        self._walk_endpoints(root, file_path, endpoints)
        return endpoints

    def extract_schemas(self, content: str, file_path: str) -> list[ASTSymbol]:
        root = parse_source(self._parser, content)
        if root is None:
            return []

        schemas: list[ASTSymbol] = []
        self._walk_schemas(root, file_path, schemas)
        return schemas

    # ------------------------------------------------------------------
    # Symbol extraction
    # ------------------------------------------------------------------

    def _walk_symbols(self, node, file_path: str, symbols: list[ASTSymbol]) -> None:
        for child in node.children:
            if child.type == "function_definition":
                sym = self._extract_function(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "class_definition":
                sym = self._extract_class(child, file_path)
                if sym:
                    symbols.append(sym)
                # Also extract methods inside the class
                body = find_first_child(child, "block")
                if body:
                    self._extract_class_methods(body, file_path, symbols)
            elif child.type == "decorated_definition":
                decorators = self._get_decorators(child)
                inner = find_first_child(child, "function_definition", "class_definition")
                if inner and inner.type == "function_definition":
                    sym = self._extract_function(inner, file_path, decorators=decorators)
                    if sym:
                        symbols.append(sym)
                elif inner and inner.type == "class_definition":
                    sym = self._extract_class(inner, file_path, decorators=decorators)
                    if sym:
                        symbols.append(sym)
                    body = find_first_child(inner, "block")
                    if body:
                        self._extract_class_methods(body, file_path, symbols)

    def _extract_function(
        self, node, file_path: str, decorators: list[str] | None = None
    ) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        is_async = any(c.type == "async" for c in node.children)
        params_node = find_first_child(node, "parameters")
        params = self._parse_params(params_node) if params_node else []
        ret = self._parse_return_type(node)
        docstring = self._get_docstring(node)

        prefix = "async def" if is_async else "def"
        sig = f"{prefix} {name}({', '.join(params)})"
        if ret:
            sig += f" -> {ret}"

        return ASTSymbol(
            name=name,
            kind="function",
            signature=sig,
            params=params,
            return_type=ret,
            docstring=docstring,
            decorators=decorators or [],
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_class(
        self, node, file_path: str, decorators: list[str] | None = None
    ) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        bases = self._parse_bases(node)
        fields = self._parse_class_fields(node)
        docstring = self._get_docstring(node)

        sig = f"class {name}"
        if bases:
            sig += f"({', '.join(bases)})"

        return ASTSymbol(
            name=name,
            kind="class",
            signature=sig,
            fields=fields,
            docstring=docstring,
            decorators=decorators or [],
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_class_methods(
        self, block_node, file_path: str, symbols: list[ASTSymbol]
    ) -> None:
        """Extract methods from a class body block."""
        for child in block_node.children:
            if child.type == "function_definition":
                sym = self._extract_function(child, file_path)
                if sym:
                    symbols.append(ASTSymbol(
                        name=sym.name,
                        kind="method",
                        signature=sym.signature,
                        params=sym.params,
                        return_type=sym.return_type,
                        docstring=sym.docstring,
                        decorators=sym.decorators,
                        line=sym.line,
                        file=sym.file,
                    ))
            elif child.type == "decorated_definition":
                decos = self._get_decorators(child)
                inner = find_first_child(child, "function_definition")
                if inner:
                    sym = self._extract_function(inner, file_path, decorators=decos)
                    if sym:
                        symbols.append(ASTSymbol(
                            name=sym.name,
                            kind="method",
                            signature=sym.signature,
                            params=sym.params,
                            return_type=sym.return_type,
                            docstring=sym.docstring,
                            decorators=sym.decorators,
                            line=sym.line,
                            file=sym.file,
                        ))

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    _ROUTE_DECORATOR_RE = re.compile(
        r"@\w+\.(route|get|post|put|delete|patch|head|options)"
        r'\(\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )

    def _walk_endpoints(self, node, file_path: str, endpoints: list[FactItem]) -> None:
        if node.type == "decorated_definition":
            for deco in find_children(node, "decorator"):
                deco_text = node_text(deco)
                match = self._ROUTE_DECORATOR_RE.search(deco_text)
                if match:
                    method = match.group(1).upper()
                    if method == "ROUTE":
                        method = "ANY"
                    path = match.group(2)
                    endpoints.append(FactItem(
                        fact_type="endpoint",
                        value=f"{method} {path}",
                        file=file_path,
                        line=node.start_point.row + 1,
                        language="python",
                    ))

        for child in node.children:
            self._walk_endpoints(child, file_path, endpoints)

    # ------------------------------------------------------------------
    # Schemas — Pydantic, SQLAlchemy, Django models
    # ------------------------------------------------------------------

    _SCHEMA_BASES = {
        "BaseModel", "Schema", "Model", "SQLModel",
        "DeclarativeBase", "Base",
    }
    _DJANGO_MODEL_BASES = {"Model", "models.Model"}

    def _walk_schemas(self, node, file_path: str, schemas: list[ASTSymbol]) -> None:
        for child in node.children:
            if child.type == "class_definition":
                self._check_schema_class(child, file_path, schemas)
            elif child.type == "decorated_definition":
                inner = find_first_child(child, "class_definition")
                if inner:
                    self._check_schema_class(inner, file_path, schemas)

        # Don't recurse deeper for schemas — only top-level classes

    def _check_schema_class(
        self, node, file_path: str, schemas: list[ASTSymbol]
    ) -> None:
        bases = self._parse_bases(node)
        is_schema = any(
            b in self._SCHEMA_BASES or b in self._DJANGO_MODEL_BASES
            for b in bases
        )
        if not is_schema:
            return

        name_node = find_first_child(node, "identifier")
        if not name_node:
            return

        name = node_text(name_node)
        fields = self._parse_class_fields(node)
        docstring = self._get_docstring(node)

        schemas.append(ASTSymbol(
            name=name,
            kind="schema",
            signature=f"class {name}({', '.join(bases)})",
            fields=fields,
            docstring=docstring,
            line=node.start_point.row + 1,
            file=file_path,
        ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_params(self, params_node) -> list[str]:
        """Parse function parameters into string list."""
        params: list[str] = []
        for child in params_node.children:
            if child.type in (
                "identifier", "typed_parameter", "default_parameter",
                "typed_default_parameter", "list_splat_pattern",
                "dictionary_splat_pattern",
            ):
                params.append(node_text(child).strip())
        return params

    def _parse_return_type(self, func_node) -> str | None:
        """Extract return type annotation from -> type."""
        ret_node = find_first_child(func_node, "type")
        if ret_node:
            return node_text(ret_node).strip()
        return None

    def _parse_bases(self, class_node) -> list[str]:
        """Extract base class names from argument_list."""
        bases: list[str] = []
        arg_list = find_first_child(class_node, "argument_list")
        if not arg_list:
            return bases
        for child in arg_list.children:
            if child.type in ("identifier", "attribute", "keyword_argument"):
                text = node_text(child).strip()
                if text:
                    bases.append(text)
        return bases

    def _parse_class_fields(self, class_node) -> list[str]:
        """Extract typed class attributes from the body."""
        fields: list[str] = []
        body = find_first_child(class_node, "block")
        if not body:
            return fields

        for child in body.children:
            if child.type == "expression_statement":
                expr = find_first_child(child, "assignment")
                if expr:
                    # Simple assignment like name: str = "default"
                    text = node_text(expr).strip()
                    fields.append(text)
                    continue
                # Type annotation: name: str
                inner = find_first_child(child, "type")
                if inner:
                    fields.append(node_text(child).strip())
            elif child.type == "type_alias_statement":
                fields.append(node_text(child).strip())

        return fields

    def _get_docstring(self, node) -> str | None:
        """Extract docstring from function/class body."""
        body = find_first_child(node, "block")
        if not body or not body.children:
            return None

        first_stmt = None
        for c in body.children:
            if c.type not in ("comment", "newline", "indent", "dedent"):
                first_stmt = c
                break

        if not first_stmt:
            return None

        # Direct string node in block (Python tree-sitter sometimes parses
        # docstrings as bare string nodes rather than expression_statement)
        if first_stmt.type == "string":
            text = node_text(first_stmt).strip("\"'").strip()
            first_line = text.split("\n")[0].strip()
            return first_line if first_line else None

        if first_stmt.type == "expression_statement":
            inner = find_first_child(first_stmt, "string", "concatenated_string")
            if inner:
                text = node_text(inner).strip("\"'").strip()
                first_line = text.split("\n")[0].strip()
                return first_line if first_line else None

        return None

    def _get_decorators(self, decorated_node) -> list[str]:
        """Extract decorator strings from a decorated definition."""
        decorators: list[str] = []
        for child in find_children(decorated_node, "decorator"):
            decorators.append(node_text(child).strip())
        return decorators
