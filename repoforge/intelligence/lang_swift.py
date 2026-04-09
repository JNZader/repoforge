"""
Swift AST Extractor — tree-sitter based analysis for Swift source files.

Extracts functions, classes, structs, enums, protocols, extensions, methods,
and Vapor/SwiftUI endpoint patterns.
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


class SwiftASTExtractor:
    """Tree-sitter based extractor for Swift files."""

    language_name: str = "swift"
    file_extensions: list[str] = [".swift"]

    def __init__(self) -> None:
        self._parser = get_parser("swift")

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
            if child.type == "function_declaration":
                sym = self._extract_function(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "class_declaration":
                sym = self._extract_class(child, file_path)
                if sym:
                    symbols.append(sym)
                body = find_first_child(child, "class_body")
                if body:
                    self._extract_members(body, file_path, symbols)
            elif child.type == "struct_declaration":
                sym = self._extract_struct(child, file_path)
                if sym:
                    symbols.append(sym)
                # try struct_body or class_body depending on grammar
                body = (
                    find_first_child(child, "class_body")
                    or find_first_child(child, "struct_body")
                )
                if body:
                    self._extract_members(body, file_path, symbols)
            elif child.type == "enum_declaration":
                sym = self._extract_enum(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "protocol_declaration":
                sym = self._extract_protocol(child, file_path)
                if sym:
                    symbols.append(sym)
                body = find_first_child(child, "protocol_body")
                if body:
                    self._extract_members(body, file_path, symbols)
            elif child.type == "extension_declaration":
                # Extension methods are important in Swift
                body = find_first_child(child, "class_body")
                if body:
                    self._extract_members(body, file_path, symbols)

    def _extract_function(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "simple_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        params = self._parse_params(node)
        ret = self._parse_return_type(node)
        comment = self._get_doc_comment(node)

        sig = f"func {name}({', '.join(params)})"
        if ret:
            sig += f" -> {ret}"

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

    def _extract_class(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "type_identifier", "simple_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        supertypes = self._get_inheritance(node)
        comment = self._get_doc_comment(node)

        sig = f"class {name}"
        if supertypes:
            sig += f": {', '.join(supertypes)}"

        return ASTSymbol(
            name=name,
            kind="class",
            signature=sig,
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_struct(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "type_identifier", "simple_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        supertypes = self._get_inheritance(node)
        fields = self._get_stored_properties(node)
        comment = self._get_doc_comment(node)

        sig = f"struct {name}"
        if supertypes:
            sig += f": {', '.join(supertypes)}"

        return ASTSymbol(
            name=name,
            kind="struct",
            signature=sig,
            fields=fields,
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_enum(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "type_identifier", "simple_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        comment = self._get_doc_comment(node)

        return ASTSymbol(
            name=name,
            kind="type",
            signature=f"enum {name}",
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_protocol(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "type_identifier", "simple_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        comment = self._get_doc_comment(node)

        return ASTSymbol(
            name=name,
            kind="interface",
            signature=f"protocol {name}",
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_members(
        self, body_node, file_path: str, symbols: list[ASTSymbol]
    ) -> None:
        """Extract methods from class/struct/protocol body."""
        for child in body_node.children:
            if child.type == "function_declaration":
                sym = self._extract_function(child, file_path)
                if sym:
                    symbols.append(ASTSymbol(
                        name=sym.name,
                        kind="method",
                        signature=sym.signature,
                        params=sym.params,
                        return_type=sym.return_type,
                        docstring=sym.docstring,
                        line=sym.line,
                        file=sym.file,
                    ))

    # ------------------------------------------------------------------
    # Endpoints — Vapor framework
    # ------------------------------------------------------------------

    _VAPOR_ROUTE_RE = re.compile(
        r'\.(get|post|put|delete|patch)\s*\(\s*"([^"]*)"',
    )

    def _walk_endpoints(self, node, file_path: str, endpoints: list[FactItem]) -> None:
        if node.type == "call_expression":
            text = node_text(node)
            match = self._VAPOR_ROUTE_RE.search(text)
            if match:
                method = match.group(1).upper()
                path = match.group(2)
                endpoints.append(FactItem(
                    fact_type="endpoint",
                    value=f"{method} {path}",
                    file=file_path,
                    line=node.start_point.row + 1,
                    language="swift",
                ))

        for child in node.children:
            self._walk_endpoints(child, file_path, endpoints)

    # ------------------------------------------------------------------
    # Schemas — CoreData NSManagedObject
    # ------------------------------------------------------------------

    _SCHEMA_BASES = {"NSManagedObject", "NSManagedObjectModel"}

    def _walk_schemas(self, node, file_path: str, schemas: list[ASTSymbol]) -> None:
        for child in node.children:
            if child.type == "class_declaration":
                supertypes = self._get_inheritance(child)
                if any(b in self._SCHEMA_BASES for b in supertypes):
                    name_node = find_first_child(
                        child, "type_identifier", "simple_identifier"
                    )
                    if name_node:
                        name = node_text(name_node)
                        schemas.append(ASTSymbol(
                            name=name,
                            kind="schema",
                            signature=f"class {name}: NSManagedObject",
                            line=child.start_point.row + 1,
                            file=file_path,
                        ))

        for child in node.children:
            self._walk_symbols(child, file_path, schemas)  # type: ignore

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_params(self, func_node) -> list[str]:
        """Parse function parameters."""
        params: list[str] = []
        params_node = find_first_child(func_node, "parameter", "function_parameters")
        if not params_node:
            # Try walking children for parameter nodes
            for child in func_node.children:
                if child.type == "parameter":
                    params.append(node_text(child).strip())
            return params

        if params_node.type == "function_parameters":
            for child in params_node.children:
                if child.type == "parameter":
                    params.append(node_text(child).strip())
        else:
            params.append(node_text(params_node).strip())
        return params

    def _parse_return_type(self, func_node) -> str | None:
        """Extract return type after -> in function signature."""
        children = list(func_node.children)
        for i, child in enumerate(children):
            if child.type == "arrow_operator" or node_text(child) == "->":
                # Next child is the return type
                if i + 1 < len(children):
                    next_child = children[i + 1]
                    if next_child.type not in ("function_body", "{"):
                        return node_text(next_child).strip()
        return None

    def _get_inheritance(self, node) -> list[str]:
        """Extract type inheritance list."""
        supertypes: list[str] = []
        for child in node.children:
            if child.type == "type_constraints" or child.type == "inheritance_specifier":
                text = node_text(child).lstrip(":").strip()
                supertypes = [t.strip() for t in text.split(",") if t.strip()]
                break
            # Some grammars use inheritance_type_list
            if "inheritance" in child.type:
                for sub in child.children:
                    if sub.type in ("type_identifier", "user_type"):
                        supertypes.append(node_text(sub).strip())
        return supertypes

    def _get_stored_properties(self, node) -> list[str]:
        """Extract stored properties from struct/class body."""
        fields: list[str] = []
        body = find_first_child(node, "class_body", "struct_body")
        if not body:
            return fields
        for child in body.children:
            if child.type in ("property_declaration", "variable_declaration"):
                text = node_text(child).strip()
                first_line = text.split("\n")[0].strip()
                fields.append(first_line)
        return fields

    def _get_doc_comment(self, node) -> str | None:
        """Get Swift doc comment (/// or /** */) preceding a node."""
        prev = node.prev_named_sibling
        if prev and prev.type == "comment":
            text = node_text(prev)
            if text.startswith("///"):
                return text.lstrip("/").strip()
            if text.startswith("/**"):
                lines = text.strip("/*").strip().split("\n")
                for line in lines:
                    cleaned = line.strip().lstrip("* ").strip()
                    if cleaned:
                        return cleaned
        return None
