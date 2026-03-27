"""
Rust AST Extractor — tree-sitter based analysis for Rust source files.

Extracts pub fn, pub struct (with fields), pub enum, pub trait, impl blocks,
and endpoint patterns for actix-web/axum route macros.
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


class RustASTExtractor:
    """Tree-sitter based extractor for Rust files."""

    language_name: str = "rust"
    file_extensions: list[str] = [".rs"]

    def __init__(self) -> None:
        self._parser = get_parser("rust")

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
        """Rust schemas are typically derived via macros — limited extraction."""
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
            if child.type == "function_item":
                sym = self._extract_function(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "struct_item":
                sym = self._extract_struct(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "enum_item":
                sym = self._extract_enum(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "trait_item":
                sym = self._extract_trait(child, file_path)
                if sym:
                    symbols.append(sym)
                # Extract trait methods
                decl_list = find_first_child(child, "declaration_list")
                if decl_list:
                    self._extract_impl_methods(decl_list, file_path, symbols)
            elif child.type == "impl_item":
                self._extract_impl(child, file_path, symbols)
            elif child.type == "const_item":
                sym = self._extract_const(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "type_item":
                sym = self._extract_type_alias(child, file_path)
                if sym:
                    symbols.append(sym)

    def _extract_function(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        is_pub = self._is_pub(node)
        params = self._parse_params(node)
        ret = self._parse_return_type(node)
        comment = self._get_doc_comment(node)

        prefix = "pub fn" if is_pub else "fn"
        sig = f"{prefix} {name}({', '.join(params)})"
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

    def _extract_struct(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "type_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        is_pub = self._is_pub(node)
        fields = self._parse_struct_fields(node)
        comment = self._get_doc_comment(node)

        prefix = "pub struct" if is_pub else "struct"
        sig = f"{prefix} {name}"

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
        name_node = find_first_child(node, "type_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        is_pub = self._is_pub(node)
        comment = self._get_doc_comment(node)
        variants = self._parse_enum_variants(node)

        prefix = "pub enum" if is_pub else "enum"
        sig = f"{prefix} {name}"

        return ASTSymbol(
            name=name,
            kind="type",
            signature=sig,
            fields=variants,
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_trait(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "type_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        is_pub = self._is_pub(node)
        comment = self._get_doc_comment(node)

        prefix = "pub trait" if is_pub else "trait"
        sig = f"{prefix} {name}"

        return ASTSymbol(
            name=name,
            kind="trait",
            signature=sig,
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_impl(self, node, file_path: str, symbols: list[ASTSymbol]) -> None:
        """Extract methods from impl blocks."""
        decl_list = find_first_child(node, "declaration_list")
        if decl_list:
            self._extract_impl_methods(decl_list, file_path, symbols)

    def _extract_impl_methods(
        self, decl_list, file_path: str, symbols: list[ASTSymbol]
    ) -> None:
        for child in decl_list.children:
            if child.type == "function_item":
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

    def _extract_const(self, node, file_path: str) -> ASTSymbol | None:
        if not self._is_pub(node):
            return None
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        sig = f"pub const {node_text(node).strip().rstrip(';')}"

        return ASTSymbol(
            name=name,
            kind="constant",
            signature=sig,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_type_alias(self, node, file_path: str) -> ASTSymbol | None:
        if not self._is_pub(node):
            return None
        name_node = find_first_child(node, "type_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        sig = f"pub type {node_text(node).strip().rstrip(';')}"

        return ASTSymbol(
            name=name,
            kind="type",
            signature=sig,
            line=node.start_point.row + 1,
            file=file_path,
        )

    # ------------------------------------------------------------------
    # Endpoints — actix-web #[get("/path")], axum Router::route
    # ------------------------------------------------------------------

    _ROUTE_MACRO_RE = re.compile(
        r"#\[(get|post|put|delete|patch|head|options)\(\s*\"([^\"]+)\"\s*\)\]",
        re.IGNORECASE,
    )

    def _walk_endpoints(self, node, file_path: str, endpoints: list[FactItem]) -> None:
        if node.type == "attribute_item":
            text = node_text(node)
            match = self._ROUTE_MACRO_RE.search(text)
            if match:
                method = match.group(1).upper()
                path = match.group(2)
                endpoints.append(FactItem(
                    fact_type="endpoint",
                    value=f"{method} {path}",
                    file=file_path,
                    line=node.start_point.row + 1,
                    language="rust",
                ))

        # Also detect axum: .route("/path", get(handler))
        if node.type == "call_expression":
            text = node_text(node)
            if ".route(" in text:
                route_match = re.search(r'\.route\(\s*"([^"]+)"', text)
                method_match = re.search(
                    r'\b(get|post|put|delete|patch)\s*\(', text
                )
                if route_match:
                    path = route_match.group(1)
                    method = method_match.group(1).upper() if method_match else "ANY"
                    endpoints.append(FactItem(
                        fact_type="endpoint",
                        value=f"{method} {path}",
                        file=file_path,
                        line=node.start_point.row + 1,
                    ))

        for child in node.children:
            self._walk_endpoints(child, file_path, endpoints)

    # ------------------------------------------------------------------
    # Schemas — diesel/sqlx macros
    # ------------------------------------------------------------------

    _TABLE_MACRO_RE = re.compile(r"table!\s*\{\s*(\w+)\s*\(", re.DOTALL)

    def _walk_schemas(self, node, file_path: str, schemas: list[ASTSymbol]) -> None:
        if node.type == "macro_invocation":
            text = node_text(node)
            match = self._TABLE_MACRO_RE.search(text)
            if match:
                schemas.append(ASTSymbol(
                    name=match.group(1),
                    kind="schema",
                    signature=f"table! {match.group(1)}",
                    line=node.start_point.row + 1,
                    file=file_path,
                ))

        for child in node.children:
            self._walk_schemas(child, file_path, schemas)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_pub(self, node) -> bool:
        return any(c.type == "visibility_modifier" for c in node.children)

    def _parse_params(self, func_node) -> list[str]:
        params_node = find_first_child(func_node, "parameters")
        if not params_node:
            return []
        params: list[str] = []
        for child in params_node.children:
            if child.type == "parameter":
                params.append(node_text(child).strip())
            elif child.type == "self_parameter":
                params.append(node_text(child).strip())
        return params

    def _parse_return_type(self, func_node) -> str | None:
        """Find -> Type in function signature."""
        children = list(func_node.children)
        arrow_idx = -1
        for i, c in enumerate(children):
            if c.type == "->":
                arrow_idx = i
                break

        if arrow_idx < 0:
            return None

        # Next non-block child after arrow is the return type
        for c in children[arrow_idx + 1:]:
            if c.type == "block":
                break
            text = node_text(c).strip()
            if text:
                return text

        return None

    def _parse_struct_fields(self, struct_node) -> list[str]:
        fields: list[str] = []
        field_list = find_first_child(struct_node, "field_declaration_list")
        if not field_list:
            return fields
        for child in field_list.children:
            if child.type == "field_declaration":
                fields.append(node_text(child).strip().rstrip(","))
        return fields

    def _parse_enum_variants(self, enum_node) -> list[str]:
        variants: list[str] = []
        body = find_first_child(enum_node, "enum_variant_list")
        if not body:
            return variants
        for child in body.children:
            if child.type == "enum_variant":
                variants.append(node_text(child).strip().rstrip(","))
        return variants

    def _get_doc_comment(self, node) -> str | None:
        """Get /// doc comment preceding a node."""
        prev = node.prev_named_sibling
        if prev and prev.type == "line_comment":
            text = node_text(prev)
            if text.startswith("///"):
                return text.lstrip("/").strip()
        return None
