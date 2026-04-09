"""
C# AST Extractor — tree-sitter based analysis for C# source files.

Extracts classes, structs, interfaces, enums, records, methods, properties,
ASP.NET endpoint attributes, and Entity Framework schemas.

NOTE: tree-sitter-language-pack may not include C# grammar.
This extractor guards against missing parser gracefully.
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


class CSharpASTExtractor:
    """Tree-sitter based extractor for C# files."""

    language_name: str = "c_sharp"
    file_extensions: list[str] = [".cs"]

    def __init__(self) -> None:
        # C# may not be available in tree-sitter-language-pack
        self._parser = get_parser("c_sharp")

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
            if child.type == "class_declaration":
                sym = self._extract_class(child, file_path)
                if sym:
                    symbols.append(sym)
                body = find_first_child(child, "declaration_list")
                if body:
                    self._extract_members(body, file_path, symbols)
            elif child.type == "struct_declaration":
                sym = self._extract_struct(child, file_path)
                if sym:
                    symbols.append(sym)
                body = find_first_child(child, "declaration_list")
                if body:
                    self._extract_members(body, file_path, symbols)
            elif child.type == "interface_declaration":
                sym = self._extract_interface(child, file_path)
                if sym:
                    symbols.append(sym)
                body = find_first_child(child, "declaration_list")
                if body:
                    self._extract_members(body, file_path, symbols)
            elif child.type == "enum_declaration":
                sym = self._extract_enum(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "record_declaration":
                sym = self._extract_record(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "namespace_declaration":
                body = find_first_child(child, "declaration_list")
                if body:
                    self._walk_symbols(body, file_path, symbols)
            elif child.type == "file_scoped_namespace_declaration":
                self._walk_symbols(child, file_path, symbols)

    def _extract_class(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        annotations = self._get_attributes(node)
        base_list = self._get_base_list(node)
        fields = self._get_fields(node)

        sig = f"class {name}"
        if base_list:
            sig += f" : {', '.join(base_list)}"

        return ASTSymbol(
            name=name,
            kind="class",
            signature=sig,
            fields=fields,
            decorators=annotations,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_struct(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        fields = self._get_fields(node)

        return ASTSymbol(
            name=name,
            kind="struct",
            signature=f"struct {name}",
            fields=fields,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_interface(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        return ASTSymbol(
            name=name,
            kind="interface",
            signature=f"interface {name}",
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_enum(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        return ASTSymbol(
            name=name,
            kind="type",
            signature=f"enum {name}",
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_record(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        params = self._parse_parameter_list(node)

        sig = f"record {name}"
        if params:
            sig += f"({', '.join(params)})"

        return ASTSymbol(
            name=name,
            kind="class",
            signature=sig,
            params=params,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_members(
        self, body_node, file_path: str, symbols: list[ASTSymbol]
    ) -> None:
        """Extract methods and nested types from a declaration_list."""
        for child in body_node.children:
            if child.type == "method_declaration":
                sym = self._extract_method(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "constructor_declaration":
                sym = self._extract_constructor(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type in (
                "class_declaration", "struct_declaration",
                "interface_declaration", "enum_declaration",
            ):
                # Nested types — recurse
                self._walk_symbols(body_node, file_path, symbols)

    def _extract_method(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        annotations = self._get_attributes(node)
        ret_type = self._get_return_type(node)
        params = self._parse_parameter_list(node)

        sig = ""
        if ret_type:
            sig = f"{ret_type} {name}({', '.join(params)})"
        else:
            sig = f"{name}({', '.join(params)})"

        return ASTSymbol(
            name=name,
            kind="method",
            signature=sig,
            params=params,
            return_type=ret_type,
            decorators=annotations,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_constructor(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        params = self._parse_parameter_list(node)

        return ASTSymbol(
            name=name,
            kind="method",
            signature=f"{name}({', '.join(params)})",
            params=params,
            line=node.start_point.row + 1,
            file=file_path,
        )

    # ------------------------------------------------------------------
    # Endpoints — ASP.NET attributes
    # ------------------------------------------------------------------

    _ROUTE_ATTR_RE = re.compile(
        r"\[(HttpGet|HttpPost|HttpPut|HttpDelete|HttpPatch|Route)"
        r'(?:\(\s*"([^"]*)"\s*\))?\]',
    )
    _ATTR_TO_METHOD = {
        "HttpGet": "GET",
        "HttpPost": "POST",
        "HttpPut": "PUT",
        "HttpDelete": "DELETE",
        "HttpPatch": "PATCH",
        "Route": "ANY",
    }

    def _walk_endpoints(self, node, file_path: str, endpoints: list[FactItem]) -> None:
        if node.type == "method_declaration":
            attributes = self._get_attributes(node)
            for attr in attributes:
                match = self._ROUTE_ATTR_RE.search(attr)
                if match:
                    method = self._ATTR_TO_METHOD.get(match.group(1), "ANY")
                    path = match.group(2) or ""
                    endpoints.append(FactItem(
                        fact_type="endpoint",
                        value=f"{method} {path}".strip(),
                        file=file_path,
                        line=node.start_point.row + 1,
                        language="c_sharp",
                    ))

        for child in node.children:
            self._walk_endpoints(child, file_path, endpoints)

    # ------------------------------------------------------------------
    # Schemas — Entity Framework [Table], DbContext
    # ------------------------------------------------------------------

    def _walk_schemas(self, node, file_path: str, schemas: list[ASTSymbol]) -> None:
        for child in node.children:
            if child.type == "class_declaration":
                attributes = self._get_attributes(child)
                has_table = any("[Table" in a for a in attributes)
                has_entity = any("DbContext" in node_text(child))
                base_list = self._get_base_list(child)
                is_entity = has_table or any("DbContext" in b for b in base_list)

                if is_entity:
                    name_node = find_first_child(child, "identifier")
                    if name_node:
                        name = node_text(name_node)
                        fields = self._get_fields(child)
                        schemas.append(ASTSymbol(
                            name=name,
                            kind="schema",
                            signature=f"class {name}",
                            fields=fields,
                            decorators=attributes,
                            line=child.start_point.row + 1,
                            file=file_path,
                        ))
            elif child.type == "namespace_declaration":
                body = find_first_child(child, "declaration_list")
                if body:
                    self._walk_schemas(body, file_path, schemas)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_attributes(self, node) -> list[str]:
        """Extract C# attributes [Attr]."""
        attrs: list[str] = []
        for child in node.children:
            if child.type == "attribute_list":
                attrs.append(node_text(child).strip())
        return attrs

    def _get_base_list(self, node) -> list[str]:
        """Extract base class/interface list."""
        bases: list[str] = []
        for child in node.children:
            if child.type == "base_list":
                text = node_text(child).lstrip(":").strip()
                bases = [b.strip() for b in text.split(",") if b.strip()]
                break
        return bases

    def _get_fields(self, node) -> list[str]:
        """Extract field/property declarations."""
        fields: list[str] = []
        body = find_first_child(node, "declaration_list")
        if not body:
            return fields
        for child in body.children:
            if child.type in ("field_declaration", "property_declaration"):
                text = node_text(child).strip().rstrip(";")
                # Keep it concise
                first_line = text.split("\n")[0].strip()
                fields.append(first_line)
        return fields

    def _get_return_type(self, node) -> str | None:
        """Extract return type from method declaration."""
        for child in node.children:
            if child.type in (
                "predefined_type", "identifier", "generic_name",
                "nullable_type", "array_type", "qualified_name",
                "void_keyword",
            ):
                text = node_text(child).strip()
                if text and text not in ("public", "private", "protected",
                                         "internal", "static", "async",
                                         "virtual", "override", "abstract"):
                    return text
        return None

    def _parse_parameter_list(self, node) -> list[str]:
        """Parse parameter list."""
        params: list[str] = []
        param_list = find_first_child(node, "parameter_list")
        if not param_list:
            return params
        for child in param_list.children:
            if child.type == "parameter":
                params.append(node_text(child).strip())
        return params
