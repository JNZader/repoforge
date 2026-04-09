"""
Kotlin AST Extractor — tree-sitter based analysis for Kotlin source files.

Extracts functions, classes, interfaces, objects, data classes, methods,
annotations, Spring/Ktor endpoints, and JPA schemas.
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


class KotlinASTExtractor:
    """Tree-sitter based extractor for Kotlin files."""

    language_name: str = "kotlin"
    file_extensions: list[str] = [".kt", ".kts"]

    def __init__(self) -> None:
        self._parser = get_parser("kotlin")

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
                # Extract methods from class body
                body = find_first_child(child, "class_body")
                if body:
                    self._extract_class_methods(body, file_path, symbols)
            elif child.type == "object_declaration":
                sym = self._extract_object(child, file_path)
                if sym:
                    symbols.append(sym)
                body = find_first_child(child, "class_body")
                if body:
                    self._extract_class_methods(body, file_path, symbols)

    def _extract_function(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "simple_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        params = self._parse_params(node)
        ret = self._parse_return_type(node)
        annotations = self._get_annotations(node)
        comment = self._get_doc_comment(node)

        is_suspend = any(
            node_text(c) == "suspend" for c in node.children
            if c.type == "modifiers" or c.type == "simple_identifier"
        )
        # Check modifiers for suspend
        mods_node = find_first_child(node, "modifiers")
        if mods_node:
            is_suspend = any(
                node_text(c) == "suspend" for c in mods_node.children
            )

        prefix = "suspend fun" if is_suspend else "fun"
        sig = f"{prefix} {name}({', '.join(params)})"
        if ret:
            sig += f": {ret}"

        return ASTSymbol(
            name=name,
            kind="function",
            signature=sig,
            params=params,
            return_type=ret,
            docstring=comment,
            decorators=annotations,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_class(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "type_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        annotations = self._get_annotations(node)
        supertypes = self._parse_supertypes(node)
        fields = self._parse_primary_constructor_params(node)
        comment = self._get_doc_comment(node)

        # Determine class kind
        mods = find_first_child(node, "modifiers")
        is_data = False
        is_sealed = False
        is_interface = False
        if mods:
            mod_text = node_text(mods)
            is_data = "data" in mod_text
            is_sealed = "sealed" in mod_text

        # Check if this is an interface declaration
        for child in node.children:
            if node_text(child) == "interface":
                is_interface = True
                break

        if is_interface:
            kind = "interface"
            prefix = "interface"
        elif is_data:
            kind = "class"
            prefix = "data class"
        elif is_sealed:
            kind = "class"
            prefix = "sealed class"
        else:
            kind = "class"
            prefix = "class"

        sig = f"{prefix} {name}"
        if supertypes:
            sig += f" : {', '.join(supertypes)}"

        return ASTSymbol(
            name=name,
            kind=kind,
            signature=sig,
            fields=fields,
            docstring=comment,
            decorators=annotations,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_object(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "type_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        comment = self._get_doc_comment(node)

        return ASTSymbol(
            name=name,
            kind="class",
            signature=f"object {name}",
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_class_methods(
        self, body_node, file_path: str, symbols: list[ASTSymbol]
    ) -> None:
        """Extract methods from a class body."""
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
                        decorators=sym.decorators,
                        line=sym.line,
                        file=sym.file,
                    ))

    # ------------------------------------------------------------------
    # Endpoints — Spring annotations & Ktor routing
    # ------------------------------------------------------------------

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

    _KTOR_ROUTE_RE = re.compile(
        r'\b(get|post|put|delete|patch)\s*\(\s*"([^"]*)"',
    )

    def _walk_endpoints(self, node, file_path: str, endpoints: list[FactItem]) -> None:
        # Spring annotations
        if node.type == "function_declaration":
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
                        language="kotlin",
                    ))

        # Ktor route calls
        if node.type == "call_expression":
            text = node_text(node)
            match = self._KTOR_ROUTE_RE.search(text)
            if match:
                method = match.group(1).upper()
                path = match.group(2)
                endpoints.append(FactItem(
                    fact_type="endpoint",
                    value=f"{method} {path}",
                    file=file_path,
                    line=node.start_point.row + 1,
                    language="kotlin",
                ))

        for child in node.children:
            self._walk_endpoints(child, file_path, endpoints)

    # ------------------------------------------------------------------
    # Schemas — JPA @Entity
    # ------------------------------------------------------------------

    def _walk_schemas(self, node, file_path: str, schemas: list[ASTSymbol]) -> None:
        for child in node.children:
            if child.type == "class_declaration":
                annotations = self._get_annotations(child)
                has_entity = any("@Entity" in a for a in annotations)
                has_table = any("@Table" in a for a in annotations)
                if has_entity or has_table:
                    name_node = find_first_child(child, "type_identifier")
                    if name_node:
                        name = node_text(name_node)
                        fields = self._parse_primary_constructor_params(child)
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

    def _parse_params(self, func_node) -> list[str]:
        """Parse function parameters."""
        params: list[str] = []
        params_node = find_first_child(func_node, "function_value_parameters")
        if not params_node:
            return params
        for child in params_node.children:
            if child.type == "parameter":
                params.append(node_text(child).strip())
        return params

    def _parse_return_type(self, func_node) -> str | None:
        """Extract return type after : in function declaration."""
        # Look for user_type or nullable_type after the parameters
        children = list(func_node.children)
        found_colon = False
        for child in children:
            if node_text(child) == ":":
                found_colon = True
                continue
            if found_colon and child.type in (
                "user_type", "nullable_type", "function_type",
                "type_identifier",
            ):
                return node_text(child).strip()
            if found_colon and child.type == "function_body":
                break
        return None

    def _parse_supertypes(self, class_node) -> list[str]:
        """Extract supertype list from delegation_specifiers."""
        supertypes: list[str] = []
        for child in class_node.children:
            if child.type == "delegation_specifiers":
                for spec in child.children:
                    if spec.type == "delegation_specifier":
                        supertypes.append(node_text(spec).strip())
        return supertypes

    def _parse_primary_constructor_params(self, class_node) -> list[str]:
        """Extract primary constructor parameters (val/var declarations)."""
        fields: list[str] = []
        ctor = find_first_child(class_node, "primary_constructor")
        if not ctor:
            return fields
        params = find_first_child(ctor, "class_parameters")
        if not params:
            return fields
        for child in params.children:
            if child.type == "class_parameter":
                fields.append(node_text(child).strip())
        return fields

    def _get_annotations(self, node) -> list[str]:
        """Extract annotations from modifiers."""
        annotations: list[str] = []
        mods = find_first_child(node, "modifiers")
        if not mods:
            return annotations
        for child in mods.children:
            if child.type == "annotation":
                annotations.append(node_text(child).strip())
        return annotations

    def _get_doc_comment(self, node) -> str | None:
        """Get KDoc comment preceding a node."""
        prev = node.prev_named_sibling
        if prev and prev.type == "multiline_comment":
            text = node_text(prev)
            if text.startswith("/**"):
                # Extract first meaningful line
                lines = text.strip("/*").strip().split("\n")
                for line in lines:
                    cleaned = line.strip().lstrip("* ").strip()
                    if cleaned:
                        return cleaned
        return None
