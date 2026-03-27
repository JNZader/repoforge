"""
Java AST Extractor — tree-sitter based analysis for Java source files.

Extracts classes, interfaces, enums, records, methods with annotations,
Spring HTTP endpoints (@GetMapping, @PostMapping, @RequestMapping),
and JPA schemas (@Entity, @Table).
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


class JavaASTExtractor:
    """Tree-sitter based extractor for Java files."""

    language_name: str = "java"
    file_extensions: list[str] = [".java"]

    def __init__(self) -> None:
        self._parser = get_parser("java")

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
                # Extract methods from class body
                body = find_first_child(child, "class_body")
                if body:
                    self._extract_methods(body, file_path, symbols)
            elif child.type == "interface_declaration":
                sym = self._extract_interface(child, file_path)
                if sym:
                    symbols.append(sym)
                body = find_first_child(child, "interface_body")
                if body:
                    self._extract_interface_methods(body, file_path, symbols)
            elif child.type == "enum_declaration":
                sym = self._extract_enum(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "record_declaration":
                sym = self._extract_record(child, file_path)
                if sym:
                    symbols.append(sym)

    def _extract_class(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        annotations = self._get_annotations(node)
        superclass = self._get_superclass(node)
        interfaces = self._get_interfaces(node)
        fields = self._get_class_fields(node)

        sig = f"class {name}"
        if superclass:
            sig += f" extends {superclass}"
        if interfaces:
            sig += f" implements {', '.join(interfaces)}"

        return ASTSymbol(
            name=name,
            kind="class",
            signature=sig,
            fields=fields,
            decorators=annotations,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_interface(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        annotations = self._get_annotations(node)

        sig = f"interface {name}"
        return ASTSymbol(
            name=name,
            kind="interface",
            signature=sig,
            decorators=annotations,
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
        params_node = find_first_child(node, "formal_parameters")
        params = self._parse_formal_params(params_node) if params_node else []

        sig = f"record {name}({', '.join(params)})"
        return ASTSymbol(
            name=name,
            kind="class",
            signature=sig,
            params=params,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_methods(
        self, body_node, file_path: str, symbols: list[ASTSymbol]
    ) -> None:
        """Extract methods from a class body."""
        for child in body_node.children:
            if child.type == "method_declaration":
                sym = self._extract_method(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "constructor_declaration":
                sym = self._extract_constructor(child, file_path)
                if sym:
                    symbols.append(sym)

    def _extract_method(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        annotations = self._get_annotations(node)
        ret_type = self._get_method_return_type(node)
        params_node = find_first_child(node, "formal_parameters")
        params = self._parse_formal_params(params_node) if params_node else []

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
        params_node = find_first_child(node, "formal_parameters")
        params = self._parse_formal_params(params_node) if params_node else []

        return ASTSymbol(
            name=name,
            kind="method",
            signature=f"{name}({', '.join(params)})",
            params=params,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_interface_methods(
        self, body_node, file_path: str, symbols: list[ASTSymbol]
    ) -> None:
        """Extract method signatures from interface body."""
        for child in body_node.children:
            if child.type == "method_declaration":
                sym = self._extract_method(child, file_path)
                if sym:
                    symbols.append(sym)

    # ------------------------------------------------------------------
    # Endpoints — Spring annotations
    # ------------------------------------------------------------------

    _MAPPING_ANNOTATIONS = {
        "GetMapping", "PostMapping", "PutMapping", "DeleteMapping",
        "PatchMapping", "RequestMapping",
    }
    _MAPPING_RE = re.compile(
        r"@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)"
        r'(?:\(\s*(?:value\s*=\s*)?["\']([^"\']*)["\'])?',
    )
    _ANNOTATION_TO_METHOD = {
        "GetMapping": "GET",
        "PostMapping": "POST",
        "PutMapping": "PUT",
        "DeleteMapping": "DELETE",
        "PatchMapping": "PATCH",
        "RequestMapping": "ANY",
    }

    def _walk_endpoints(self, node, file_path: str, endpoints: list[FactItem]) -> None:
        """Walk AST looking for Spring mapping annotations."""
        if node.type == "method_declaration":
            annotations = self._get_annotations(node)
            for ann in annotations:
                match = self._MAPPING_RE.search(ann)
                if match:
                    method = self._ANNOTATION_TO_METHOD.get(match.group(1), "ANY")
                    path = match.group(2) or ""
                    endpoints.append(FactItem(
                        fact_type="endpoint",
                        value=f"{method} {path}".strip(),
                        file=file_path,
                        line=node.start_point.row + 1,
                        language="java",
                    ))

        for child in node.children:
            self._walk_endpoints(child, file_path, endpoints)

    # ------------------------------------------------------------------
    # Schemas — JPA @Entity, @Table
    # ------------------------------------------------------------------

    def _walk_schemas(self, node, file_path: str, schemas: list[ASTSymbol]) -> None:
        for child in node.children:
            if child.type == "class_declaration":
                annotations = self._get_annotations(child)
                has_entity = any("@Entity" in a for a in annotations)
                has_table = any("@Table" in a for a in annotations)
                if has_entity or has_table:
                    name_node = find_first_child(child, "identifier")
                    if name_node:
                        name = node_text(name_node)
                        fields = self._get_class_fields(child)
                        schemas.append(ASTSymbol(
                            name=name,
                            kind="schema",
                            signature=f"@Entity class {name}",
                            fields=fields,
                            decorators=annotations,
                            line=child.start_point.row + 1,
                            file=file_path,
                        ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_annotations(self, node) -> list[str]:
        """Extract annotations from modifiers node."""
        annotations: list[str] = []
        mods = find_first_child(node, "modifiers")
        if not mods:
            return annotations
        for child in mods.children:
            if child.type in ("annotation", "marker_annotation"):
                annotations.append(node_text(child).strip())
        return annotations

    def _get_superclass(self, node) -> str:
        """Extract extends clause."""
        for child in node.children:
            if child.type == "superclass":
                return node_text(child).replace("extends", "").strip()
        return ""

    def _get_interfaces(self, node) -> list[str]:
        """Extract implements clause."""
        for child in node.children:
            if child.type == "super_interfaces":
                text = node_text(child).replace("implements", "").strip()
                return [t.strip() for t in text.split(",") if t.strip()]
        return []

    def _get_class_fields(self, node) -> list[str]:
        """Extract field declarations from class body."""
        fields: list[str] = []
        body = find_first_child(node, "class_body")
        if not body:
            return fields
        for child in body.children:
            if child.type == "field_declaration":
                text = node_text(child).strip().rstrip(";")
                fields.append(text)
        return fields

    def _get_method_return_type(self, node) -> str | None:
        """Extract return type from method declaration."""
        # Return type is before the method name
        for child in node.children:
            if child.type in (
                "void_type", "type_identifier", "generic_type",
                "array_type", "integral_type", "floating_point_type",
                "boolean_type", "scoped_type_identifier",
            ):
                return node_text(child).strip()
        return None

    def _parse_formal_params(self, params_node) -> list[str]:
        """Parse formal parameter list."""
        params: list[str] = []
        for child in params_node.children:
            if child.type == "formal_parameter" or child.type == "spread_parameter":
                params.append(node_text(child).strip())
        return params
