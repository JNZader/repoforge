"""
PHP AST Extractor — tree-sitter based analysis for PHP source files.

Extracts functions, classes, interfaces, traits, methods,
Laravel/Symfony route definitions, and Eloquent/Doctrine schemas.
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


class PHPASTExtractor:
    """Tree-sitter based extractor for PHP files."""

    language_name: str = "php"
    file_extensions: list[str] = [".php"]

    def __init__(self) -> None:
        self._parser = get_parser("php")

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
            elif child.type == "class_declaration":
                sym = self._extract_class(child, file_path)
                if sym:
                    symbols.append(sym)
                body = find_first_child(child, "declaration_list")
                if body:
                    self._extract_class_members(body, file_path, symbols)
            elif child.type == "interface_declaration":
                sym = self._extract_interface(child, file_path)
                if sym:
                    symbols.append(sym)
                body = find_first_child(child, "declaration_list")
                if body:
                    self._extract_class_members(body, file_path, symbols)
            elif child.type == "trait_declaration":
                sym = self._extract_trait(child, file_path)
                if sym:
                    symbols.append(sym)
                body = find_first_child(child, "declaration_list")
                if body:
                    self._extract_class_members(body, file_path, symbols)
            elif child.type == "enum_declaration":
                sym = self._extract_enum(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "namespace_definition":
                body = find_first_child(child, "compound_statement")
                if body:
                    self._walk_symbols(body, file_path, symbols)
            # PHP files wrapped in program node
            elif child.type == "program":
                self._walk_symbols(child, file_path, symbols)

    def _extract_function(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "name")
        if not name_node:
            return None

        name = node_text(name_node)
        params = self._parse_params(node)
        ret = self._parse_return_type(node)
        comment = self._get_doc_comment(node)

        sig = f"function {name}({', '.join(params)})"
        if ret:
            sig += f": {ret}"

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
        name_node = find_first_child(node, "name")
        if not name_node:
            return None

        name = node_text(name_node)
        bases = self._get_base_clause(node)
        interfaces = self._get_interfaces(node)
        fields = self._get_class_properties(node)
        comment = self._get_doc_comment(node)

        sig = f"class {name}"
        if bases:
            sig += f" extends {bases}"
        if interfaces:
            sig += f" implements {', '.join(interfaces)}"

        return ASTSymbol(
            name=name,
            kind="class",
            signature=sig,
            fields=fields,
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_interface(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "name")
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

    def _extract_trait(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "name")
        if not name_node:
            return None

        name = node_text(name_node)
        return ASTSymbol(
            name=name,
            kind="trait",
            signature=f"trait {name}",
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_enum(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "name")
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

    def _extract_class_members(
        self, body_node, file_path: str, symbols: list[ASTSymbol]
    ) -> None:
        """Extract methods from class/interface/trait body."""
        for child in body_node.children:
            if child.type == "method_declaration":
                sym = self._extract_method(child, file_path)
                if sym:
                    symbols.append(sym)

    def _extract_method(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "name")
        if not name_node:
            return None

        name = node_text(name_node)
        params = self._parse_params(node)
        ret = self._parse_return_type(node)
        visibility = self._get_visibility(node)
        comment = self._get_doc_comment(node)

        prefix = f"{visibility} function" if visibility else "function"
        sig = f"{prefix} {name}({', '.join(params)})"
        if ret:
            sig += f": {ret}"

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
    # Endpoints — Laravel Route:: and Symfony annotations
    # ------------------------------------------------------------------

    _ROUTE_CALL_RE = re.compile(
        r"Route::(get|post|put|delete|patch|any)\s*\(\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE,
    )

    _SYMFONY_ROUTE_RE = re.compile(
        r"#\[Route\s*\(\s*['\"]([^'\"]+)['\"]"
        r"(?:.*?methods?\s*[=:]\s*\[?\s*['\"](\w+)['\"])?"
    )

    def _walk_endpoints(self, node, file_path: str, endpoints: list[FactItem]) -> None:
        # Detect Laravel Route:: calls
        if node.type in ("expression_statement", "member_call_expression"):
            text = node_text(node)
            match = self._ROUTE_CALL_RE.search(text)
            if match:
                method = match.group(1).upper()
                if method == "ANY":
                    method = "ANY"
                path = match.group(2)
                endpoints.append(FactItem(
                    fact_type="endpoint",
                    value=f"{method} {path}",
                    file=file_path,
                    line=node.start_point.row + 1,
                    language="php",
                ))

        # Detect Symfony #[Route] attributes
        if node.type == "attribute_list":
            text = node_text(node)
            match = self._SYMFONY_ROUTE_RE.search(text)
            if match:
                path = match.group(1)
                method = match.group(2).upper() if match.group(2) else "ANY"
                endpoints.append(FactItem(
                    fact_type="endpoint",
                    value=f"{method} {path}",
                    file=file_path,
                    line=node.start_point.row + 1,
                    language="php",
                ))

        for child in node.children:
            self._walk_endpoints(child, file_path, endpoints)

    # ------------------------------------------------------------------
    # Schemas — Eloquent models, Doctrine entities
    # ------------------------------------------------------------------

    _MODEL_BASES = {"Model", "Eloquent", "Authenticatable"}

    def _walk_schemas(self, node, file_path: str, schemas: list[ASTSymbol]) -> None:
        for child in node.children:
            if child.type == "class_declaration":
                base = self._get_base_clause(child)
                if base and any(b in base for b in self._MODEL_BASES):
                    name_node = find_first_child(child, "name")
                    if name_node:
                        name = node_text(name_node)
                        fields = self._get_class_properties(child)
                        schemas.append(ASTSymbol(
                            name=name,
                            kind="schema",
                            signature=f"class {name} extends {base}",
                            fields=fields,
                            line=child.start_point.row + 1,
                            file=file_path,
                        ))
            elif child.type == "namespace_definition":
                body = find_first_child(child, "compound_statement")
                if body:
                    self._walk_schemas(body, file_path, schemas)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_params(self, func_node) -> list[str]:
        """Parse function/method parameters."""
        params: list[str] = []
        params_node = find_first_child(func_node, "formal_parameters")
        if not params_node:
            return params
        for child in params_node.children:
            if child.type in ("simple_parameter", "variadic_parameter",
                              "property_promotion_parameter"):
                params.append(node_text(child).strip())
        return params

    def _parse_return_type(self, func_node) -> str | None:
        """Extract return type after : in function signature."""
        for child in func_node.children:
            if child.type in ("named_type", "optional_type", "union_type",
                              "intersection_type", "primitive_type"):
                return node_text(child).strip()
            # Also handle : ReturnType pattern
            if child.type == "return_type":
                return node_text(child).lstrip(":").strip()
        return None

    def _get_base_clause(self, class_node) -> str:
        """Extract extends clause."""
        for child in class_node.children:
            if child.type == "base_clause":
                text = node_text(child)
                return text.replace("extends", "").strip()
        return ""

    def _get_interfaces(self, class_node) -> list[str]:
        """Extract implements clause."""
        for child in class_node.children:
            if child.type == "class_interface_clause":
                text = node_text(child).replace("implements", "").strip()
                return [t.strip() for t in text.split(",") if t.strip()]
        return []

    def _get_class_properties(self, class_node) -> list[str]:
        """Extract property declarations from class body."""
        fields: list[str] = []
        body = find_first_child(class_node, "declaration_list")
        if not body:
            return fields
        for child in body.children:
            if child.type == "property_declaration":
                text = node_text(child).strip().rstrip(";")
                fields.append(text)
        return fields

    def _get_visibility(self, node) -> str:
        """Get visibility modifier (public, private, protected)."""
        for child in node.children:
            if child.type == "visibility_modifier":
                return node_text(child).strip()
        return ""

    def _get_doc_comment(self, node) -> str | None:
        """Get PHPDoc comment preceding a node."""
        prev = node.prev_named_sibling
        if prev and prev.type == "comment":
            text = node_text(prev)
            if text.startswith("/**"):
                lines = text.strip("/*").strip().split("\n")
                for line in lines:
                    cleaned = line.strip().lstrip("* ").strip()
                    if cleaned and not cleaned.startswith("@"):
                        return cleaned
        return None
