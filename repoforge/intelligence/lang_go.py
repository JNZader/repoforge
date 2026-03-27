"""
Go AST Extractor — tree-sitter based analysis for Go source files.

Extracts functions (with params + return types), methods (with receiver),
types (struct fields), interfaces, constants, HTTP endpoints, and SQL schemas.
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


class GoASTExtractor:
    """Tree-sitter based extractor for Go files."""

    language_name: str = "go"
    file_extensions: list[str] = [".go"]

    def __init__(self) -> None:
        self._parser = get_parser("go")

    def extract_symbols(self, content: str, file_path: str) -> list[ASTSymbol]:
        root = parse_source(self._parser, content)
        if root is None:
            return []

        symbols: list[ASTSymbol] = []
        for child in root.children:
            if child.type == "function_declaration":
                sym = self._extract_function(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "method_declaration":
                sym = self._extract_method(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "type_declaration":
                syms = self._extract_type_decl(child, file_path)
                symbols.extend(syms)
            elif child.type in ("const_declaration", "var_declaration"):
                syms = self._extract_var_const(child, file_path)
                symbols.extend(syms)

        return symbols

    def extract_endpoints(self, content: str, file_path: str) -> list[FactItem]:
        root = parse_source(self._parser, content)
        if root is None:
            return []

        endpoints: list[FactItem] = []
        self._walk_for_endpoints(root, file_path, endpoints)
        return endpoints

    def extract_schemas(self, content: str, file_path: str) -> list[ASTSymbol]:
        """Extract SQL CREATE TABLE from string literals."""
        root = parse_source(self._parser, content)
        if root is None:
            return []

        schemas: list[ASTSymbol] = []
        self._walk_for_schemas(root, file_path, schemas)
        return schemas

    # ------------------------------------------------------------------
    # Functions
    # ------------------------------------------------------------------

    def _extract_function(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        params_node = find_first_child(node, "parameter_list")
        params = self._parse_params(params_node) if params_node else []
        ret = self._parse_return_type(node)
        comment = self._get_preceding_comment(node)

        sig = f"func {name}({', '.join(params)})"
        if ret:
            sig += f" {ret}"

        return ASTSymbol(
            name=name,
            kind="function",
            signature=sig,
            params=params,
            return_type=ret,
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    # ------------------------------------------------------------------
    # Methods (with receiver)
    # ------------------------------------------------------------------

    def _extract_method(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "field_identifier")
        if not name_node:
            return None

        name = node_text(name_node)

        # Receiver is the first parameter_list
        param_lists = find_children(node, "parameter_list")
        receiver = ""
        params: list[str] = []
        if len(param_lists) >= 1:
            receiver = node_text(param_lists[0])
        if len(param_lists) >= 2:
            params = self._parse_params(param_lists[1])

        ret = self._parse_return_type(node)
        comment = self._get_preceding_comment(node)

        sig = f"func {receiver} {name}({', '.join(params)})"
        if ret:
            sig += f" {ret}"

        return ASTSymbol(
            name=name,
            kind="method",
            signature=sig,
            params=params,
            return_type=ret,
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    # ------------------------------------------------------------------
    # Types: struct, interface
    # ------------------------------------------------------------------

    def _extract_type_decl(self, node, file_path: str) -> list[ASTSymbol]:
        symbols: list[ASTSymbol] = []
        for spec in find_children(node, "type_spec"):
            name_node = find_first_child(spec, "type_identifier")
            if not name_node:
                continue

            name = node_text(name_node)
            struct_node = find_first_child(spec, "struct_type")
            iface_node = find_first_child(spec, "interface_type")
            comment = self._get_preceding_comment(node)

            if struct_node:
                fields = self._parse_struct_fields(struct_node)
                sig = f"type {name} struct"
                symbols.append(ASTSymbol(
                    name=name,
                    kind="struct",
                    signature=sig,
                    fields=fields,
                    docstring=comment,
                    line=node.start_point.row + 1,
                    file=file_path,
                ))
            elif iface_node:
                methods = self._parse_interface_methods(iface_node)
                sig = f"type {name} interface"
                symbols.append(ASTSymbol(
                    name=name,
                    kind="interface",
                    signature=sig,
                    fields=methods,
                    docstring=comment,
                    line=node.start_point.row + 1,
                    file=file_path,
                ))
            else:
                # Type alias or other type definition
                type_val = node_text(spec)
                sig = f"type {type_val}"
                symbols.append(ASTSymbol(
                    name=name,
                    kind="type",
                    signature=sig,
                    docstring=comment,
                    line=node.start_point.row + 1,
                    file=file_path,
                ))

        return symbols

    # ------------------------------------------------------------------
    # Var / Const
    # ------------------------------------------------------------------

    def _extract_var_const(self, node, file_path: str) -> list[ASTSymbol]:
        symbols: list[ASTSymbol] = []
        kind = "constant" if node.type == "const_declaration" else "variable"
        keyword = "const" if kind == "constant" else "var"

        for spec in find_children(node, "const_spec", "var_spec"):
            name_node = find_first_child(spec, "identifier")
            if not name_node:
                continue
            name = node_text(name_node)
            # Only exported (uppercase first letter in Go)
            if not name[0].isupper():
                continue

            sig = f"{keyword} {node_text(spec)}"
            symbols.append(ASTSymbol(
                name=name,
                kind=kind,
                signature=sig.strip(),
                line=node.start_point.row + 1,
                file=file_path,
            ))

        return symbols

    # ------------------------------------------------------------------
    # Endpoints — http.HandleFunc, mux.HandleFunc, e.GET/POST patterns
    # ------------------------------------------------------------------

    # Patterns: s.mux.HandleFunc("METHOD /path", handler)
    #           http.HandleFunc("/path", handler)
    #           e.GET("/path", handler), r.POST("/path", handler)
    _HANDLE_METHODS = {"HandleFunc", "Handle", "GET", "POST", "PUT", "DELETE", "PATCH"}
    _HTTP_METHOD_PATTERN = re.compile(
        r"^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(/\S*)"
    )

    def _walk_for_endpoints(self, node, file_path: str, endpoints: list[FactItem]) -> None:
        if node.type == "call_expression":
            self._check_endpoint_call(node, file_path, endpoints)

        for child in node.children:
            self._walk_for_endpoints(child, file_path, endpoints)

    def _check_endpoint_call(
        self, node, file_path: str, endpoints: list[FactItem]
    ) -> None:
        func_node = find_first_child(node, "selector_expression")
        if not func_node:
            return

        # Get the method name (last identifier in the selector)
        field_node = find_first_child(func_node, "field_identifier")
        if not field_node:
            return
        method_name = node_text(field_node)

        if method_name not in self._HANDLE_METHODS:
            return

        # Get first argument (the route string)
        args = find_first_child(node, "argument_list")
        if not args:
            return

        first_arg = None
        for c in args.children:
            if c.type == "interpreted_string_literal" or c.type == "raw_string_literal":
                first_arg = c
                break

        if not first_arg:
            return

        route = node_text(first_arg).strip('"').strip("`")

        # Determine HTTP method
        if method_name in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"):
            http_method = method_name
            endpoint_value = f"{http_method} {route}"
        else:
            # HandleFunc/Handle — check if route has "METHOD /path" pattern
            match = self._HTTP_METHOD_PATTERN.match(route)
            if match:
                endpoint_value = route
            else:
                endpoint_value = f"ANY {route}"

        endpoints.append(FactItem(
            fact_type="endpoint",
            value=endpoint_value,
            file=file_path,
            line=node.start_point.row + 1,
            language="go",
        ))

    # ------------------------------------------------------------------
    # Schemas — SQL CREATE TABLE in string literals
    # ------------------------------------------------------------------

    _CREATE_TABLE_RE = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?",
        re.IGNORECASE,
    )

    def _walk_for_schemas(self, node, file_path: str, schemas: list[ASTSymbol]) -> None:
        if node.type in ("interpreted_string_literal", "raw_string_literal"):
            text = node_text(node)
            for m in self._CREATE_TABLE_RE.finditer(text):
                schemas.append(ASTSymbol(
                    name=m.group(1),
                    kind="schema",
                    signature=f"CREATE TABLE {m.group(1)}",
                    line=node.start_point.row + 1,
                    file=file_path,
                ))

        for child in node.children:
            self._walk_for_schemas(child, file_path, schemas)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_params(self, param_list_node) -> list[str]:
        """Parse a Go parameter list into individual param strings."""
        params: list[str] = []
        for child in param_list_node.children:
            if child.type == "parameter_declaration":
                params.append(node_text(child).strip())
        return params

    def _parse_return_type(self, func_node) -> str | None:
        """Extract return type from function/method node."""
        # Look for result types after parameter lists
        children = list(func_node.children)
        # Find the last parameter_list index
        last_param_idx = -1
        for i, c in enumerate(children):
            if c.type == "parameter_list":
                last_param_idx = i

        if last_param_idx < 0:
            return None

        # Everything between last param_list and block is the return type
        ret_parts = []
        for c in children[last_param_idx + 1:]:
            if c.type == "block":
                break
            text = node_text(c).strip()
            if text:
                ret_parts.append(text)

        return " ".join(ret_parts) if ret_parts else None

    def _parse_struct_fields(self, struct_node) -> list[str]:
        """Extract struct field declarations."""
        fields: list[str] = []
        field_list = find_first_child(struct_node, "field_declaration_list")
        if not field_list:
            return fields

        for child in field_list.children:
            if child.type == "field_declaration":
                fields.append(node_text(child).strip())

        return fields

    def _parse_interface_methods(self, iface_node) -> list[str]:
        """Extract interface method signatures."""
        methods: list[str] = []
        # Interface body contains method specs
        for child in iface_node.children:
            if child.type == "method_elem":
                methods.append(node_text(child).strip())
            # Also handle embedded types in interfaces
            elif child.type == "type_elem":
                methods.append(node_text(child).strip())

        return methods

    def _get_preceding_comment(self, node) -> str | None:
        """Get the comment block immediately preceding a node."""
        # In Go tree-sitter, comments are siblings
        parent = node.parent
        if not parent:
            return None

        prev = node.prev_named_sibling
        if prev and prev.type == "comment":
            text = node_text(prev).lstrip("/").strip()
            return text if text else None

        return None
