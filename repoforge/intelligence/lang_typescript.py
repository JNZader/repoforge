"""
TypeScript AST Extractor — tree-sitter based analysis for TypeScript source files.

Extracts functions, classes, interfaces, type aliases, exported consts,
endpoints (app.get(), router.post()), and schemas (Zod, Prisma, TypeORM).
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


class TypeScriptASTExtractor:
    """Tree-sitter based extractor for TypeScript files."""

    language_name: str = "typescript"
    file_extensions: list[str] = [".ts", ".tsx"]

    def __init__(self) -> None:
        self._parser = get_parser("typescript")

    def extract_symbols(self, content: str, file_path: str) -> list[ASTSymbol]:
        root = parse_source(self._parser, content)
        if root is None:
            return []

        symbols: list[ASTSymbol] = []
        for child in root.children:
            if child.type == "export_statement":
                self._extract_export(child, file_path, symbols)
            elif child.type == "function_declaration":
                sym = self._extract_function(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "class_declaration":
                sym = self._extract_class(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "interface_declaration":
                sym = self._extract_interface(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "type_alias_declaration":
                sym = self._extract_type_alias(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "lexical_declaration":
                syms = self._extract_const(child, file_path)
                symbols.extend(syms)

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
    # Export statement unwrapping
    # ------------------------------------------------------------------

    def _extract_export(self, node, file_path: str, symbols: list[ASTSymbol]) -> None:
        """Unwrap export statement and extract inner declaration."""
        for child in node.children:
            if child.type == "function_declaration":
                sym = self._extract_function(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "class_declaration":
                sym = self._extract_class(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "interface_declaration":
                sym = self._extract_interface(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "type_alias_declaration":
                sym = self._extract_type_alias(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "lexical_declaration":
                syms = self._extract_const(child, file_path)
                symbols.extend(syms)
            elif child.type == "abstract_class_declaration":
                sym = self._extract_class(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "enum_declaration":
                sym = self._extract_enum(child, file_path)
                if sym:
                    symbols.append(sym)

    # ------------------------------------------------------------------
    # Functions
    # ------------------------------------------------------------------

    def _extract_function(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        is_async = any(c.type == "async" for c in node.children)
        params = self._parse_params(node)
        ret = self._parse_return_type(node)

        prefix = "async function" if is_async else "function"
        sig = f"{prefix} {name}({', '.join(params)})"
        if ret:
            sig += f": {ret}"

        return ASTSymbol(
            name=name,
            kind="function",
            signature=sig,
            params=params,
            return_type=ret,
            line=node.start_point.row + 1,
            file=file_path,
        )

    # ------------------------------------------------------------------
    # Classes
    # ------------------------------------------------------------------

    def _extract_class(self, node, file_path: str) -> ASTSymbol | None:
        # TS uses type_identifier, JS uses identifier for class names
        name_node = find_first_child(node, "type_identifier", "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        # Extract heritage (extends/implements)
        heritage = self._parse_heritage(node)
        fields = self._parse_class_body(node)

        sig = f"class {name}"
        if heritage:
            sig += f" {heritage}"

        return ASTSymbol(
            name=name,
            kind="class",
            signature=sig,
            fields=fields,
            line=node.start_point.row + 1,
            file=file_path,
        )

    # ------------------------------------------------------------------
    # Interfaces
    # ------------------------------------------------------------------

    def _extract_interface(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "type_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        fields = self._parse_interface_body(node)
        extends = self._parse_extends(node)

        sig = f"interface {name}"
        if extends:
            sig += f" extends {extends}"

        return ASTSymbol(
            name=name,
            kind="interface",
            signature=sig,
            fields=fields,
            line=node.start_point.row + 1,
            file=file_path,
        )

    # ------------------------------------------------------------------
    # Type aliases
    # ------------------------------------------------------------------

    def _extract_type_alias(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "type_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        sig = f"type {node_text(node).strip().rstrip(';')}"

        return ASTSymbol(
            name=name,
            kind="type",
            signature=sig,
            line=node.start_point.row + 1,
            file=file_path,
        )

    # ------------------------------------------------------------------
    # Constants
    # ------------------------------------------------------------------

    def _extract_const(self, node, file_path: str) -> list[ASTSymbol]:
        symbols: list[ASTSymbol] = []
        for decl in find_children(node, "variable_declarator"):
            name_node = find_first_child(decl, "identifier")
            if not name_node:
                continue
            name = node_text(name_node)
            # Only include ALL_CAPS or PascalCase exports
            if not (name[0].isupper() or name.isupper()):
                continue

            sig = f"const {node_text(decl).strip()}"
            symbols.append(ASTSymbol(
                name=name,
                kind="constant",
                signature=sig,
                line=node.start_point.row + 1,
                file=file_path,
            ))
        return symbols

    # ------------------------------------------------------------------
    # Enums
    # ------------------------------------------------------------------

    def _extract_enum(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        sig = f"enum {name}"

        return ASTSymbol(
            name=name,
            kind="type",
            signature=sig,
            line=node.start_point.row + 1,
            file=file_path,
        )

    # ------------------------------------------------------------------
    # Endpoints — app.get('/path'), router.post('/path')
    # ------------------------------------------------------------------

    _ENDPOINT_RE = re.compile(
        r"\.(get|post|put|delete|patch|head|options|all|use)\s*\(\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE,
    )

    def _walk_endpoints(self, node, file_path: str, endpoints: list[FactItem]) -> None:
        if node.type == "expression_statement":
            text = node_text(node)
            for match in self._ENDPOINT_RE.finditer(text):
                method = match.group(1).upper()
                path = match.group(2)
                if method in ("USE", "ALL"):
                    method = "ANY"
                endpoints.append(FactItem(
                    fact_type="endpoint",
                    value=f"{method} {path}",
                    file=file_path,
                    line=node.start_point.row + 1,
                    language="typescript",
                ))

        for child in node.children:
            self._walk_endpoints(child, file_path, endpoints)

    # ------------------------------------------------------------------
    # Schemas — Zod, Prisma, TypeORM
    # ------------------------------------------------------------------

    _ZOD_RE = re.compile(r"z\.\w+\(")

    def _walk_schemas(self, node, file_path: str, schemas: list[ASTSymbol]) -> None:
        """Find Zod schemas and decorated classes (TypeORM @Entity)."""
        for child in node.children:
            if child.type in ("export_statement", "lexical_declaration"):
                self._check_zod_schema(child, file_path, schemas)
            # TypeORM: @Entity() class User { ... }
            if child.type == "export_statement":
                for inner in child.children:
                    if inner.type == "class_declaration":
                        if self._has_entity_decorator(child):
                            name_node = find_first_child(inner, "type_identifier")
                            if name_node:
                                schemas.append(ASTSymbol(
                                    name=node_text(name_node),
                                    kind="schema",
                                    signature=f"@Entity class {node_text(name_node)}",
                                    line=child.start_point.row + 1,
                                    file=file_path,
                                ))

    def _check_zod_schema(self, node, file_path: str, schemas: list[ASTSymbol]) -> None:
        """Check if a variable declaration uses z.object(), z.string(), etc."""
        text = node_text(node)
        if not self._ZOD_RE.search(text):
            return

        # Find variable name
        for decl in find_children(node, "variable_declarator", "lexical_declaration"):
            if decl.type == "lexical_declaration":
                for sub in find_children(decl, "variable_declarator"):
                    self._extract_zod_decl(sub, file_path, schemas)
            else:
                self._extract_zod_decl(decl, file_path, schemas)

        # Direct check on the node itself
        for decl in find_children(node, "variable_declarator"):
            self._extract_zod_decl(decl, file_path, schemas)

    def _extract_zod_decl(self, decl, file_path: str, schemas: list[ASTSymbol]) -> None:
        name_node = find_first_child(decl, "identifier")
        if not name_node:
            return
        name = node_text(name_node)
        if self._ZOD_RE.search(node_text(decl)):
            schemas.append(ASTSymbol(
                name=name,
                kind="schema",
                signature=f"const {name} = z.object(...)",
                line=decl.start_point.row + 1,
                file=file_path,
            ))

    def _has_entity_decorator(self, node) -> bool:
        text = node_text(node)
        return "@Entity" in text

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_params(self, func_node) -> list[str]:
        """Extract function parameters."""
        params: list[str] = []
        formal = find_first_child(func_node, "formal_parameters")
        if not formal:
            return params
        for child in formal.children:
            if child.type in (
                "required_parameter", "optional_parameter",
                "rest_pattern",
            ):
                params.append(node_text(child).strip())
        return params

    def _parse_return_type(self, func_node) -> str | None:
        """Extract return type annotation."""
        ann = find_first_child(func_node, "type_annotation")
        if ann:
            return node_text(ann).lstrip(":").strip()
        return None

    def _parse_heritage(self, class_node) -> str:
        """Parse extends/implements clauses."""
        parts: list[str] = []
        for child in class_node.children:
            if child.type == "class_heritage":
                parts.append(node_text(child).strip())
        return " ".join(parts)

    def _parse_extends(self, iface_node) -> str:
        """Parse extends clause for interfaces."""
        for child in iface_node.children:
            if child.type == "extends_type_clause":
                return node_text(child).replace("extends", "").strip()
        return ""

    def _parse_class_body(self, class_node) -> list[str]:
        """Extract field declarations from class body."""
        fields: list[str] = []
        body = find_first_child(class_node, "class_body")
        if not body:
            return fields
        for child in body.children:
            if child.type in (
                "public_field_definition", "property_definition",
                "field_definition",
            ):
                fields.append(node_text(child).strip().rstrip(";"))
        return fields

    def _parse_interface_body(self, iface_node) -> list[str]:
        """Extract property signatures from interface body."""
        fields: list[str] = []
        body = find_first_child(iface_node, "interface_body", "object_type")
        if not body:
            return fields
        for child in body.children:
            if child.type in ("property_signature", "method_signature"):
                fields.append(node_text(child).strip().rstrip(";"))
        return fields
