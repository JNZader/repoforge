"""
Ruby AST Extractor — tree-sitter based analysis for Ruby source files.

Extracts methods (def), classes, modules, Rails endpoints,
and ActiveRecord schemas.
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


class RubyASTExtractor:
    """Tree-sitter based extractor for Ruby files."""

    language_name: str = "ruby"
    file_extensions: list[str] = [".rb"]

    def __init__(self) -> None:
        self._parser = get_parser("ruby")

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
            if child.type == "method":
                sym = self._extract_method(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "singleton_method":
                sym = self._extract_singleton_method(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "class":
                sym = self._extract_class(child, file_path)
                if sym:
                    symbols.append(sym)
                # Extract methods from class body
                body = find_first_child(child, "body_statement")
                if body:
                    self._extract_class_methods(body, file_path, symbols)
            elif child.type == "module":
                sym = self._extract_module(child, file_path)
                if sym:
                    symbols.append(sym)
                body = find_first_child(child, "body_statement")
                if body:
                    self._walk_symbols(body, file_path, symbols)

    def _extract_method(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        params = self._parse_params(node)
        comment = self._get_comment(node)

        sig = f"def {name}"
        if params:
            sig += f"({', '.join(params)})"

        return ASTSymbol(
            name=name,
            kind="function",
            signature=sig,
            params=params,
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_singleton_method(self, node, file_path: str) -> ASTSymbol | None:
        """Extract self.method_name definitions."""
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        params = self._parse_params(node)
        comment = self._get_comment(node)

        sig = f"def self.{name}"
        if params:
            sig += f"({', '.join(params)})"

        return ASTSymbol(
            name=name,
            kind="function",
            signature=sig,
            params=params,
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_class(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "constant", "scope_resolution")
        if not name_node:
            return None

        name = node_text(name_node)
        superclass = self._get_superclass(node)
        comment = self._get_comment(node)

        sig = f"class {name}"
        if superclass:
            sig += f" < {superclass}"

        return ASTSymbol(
            name=name,
            kind="class",
            signature=sig,
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_module(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "constant", "scope_resolution")
        if not name_node:
            return None

        name = node_text(name_node)
        comment = self._get_comment(node)

        return ASTSymbol(
            name=name,
            kind="class",
            signature=f"module {name}",
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_class_methods(
        self, body_node, file_path: str, symbols: list[ASTSymbol]
    ) -> None:
        """Extract methods from a class body."""
        for child in body_node.children:
            if child.type == "method":
                sym = self._extract_method(child, file_path)
                if sym:
                    symbols.append(ASTSymbol(
                        name=sym.name,
                        kind="method",
                        signature=sym.signature,
                        params=sym.params,
                        docstring=sym.docstring,
                        line=sym.line,
                        file=sym.file,
                    ))
            elif child.type == "singleton_method":
                sym = self._extract_singleton_method(child, file_path)
                if sym:
                    symbols.append(ASTSymbol(
                        name=sym.name,
                        kind="method",
                        signature=sym.signature,
                        params=sym.params,
                        docstring=sym.docstring,
                        line=sym.line,
                        file=sym.file,
                    ))

    # ------------------------------------------------------------------
    # Endpoints — Rails routes
    # ------------------------------------------------------------------

    _ROUTE_RE = re.compile(
        r"\b(get|post|put|patch|delete)\s+['\"]([^'\"]+)['\"]",
    )

    def _walk_endpoints(self, node, file_path: str, endpoints: list[FactItem]) -> None:
        if node.type == "call":
            text = node_text(node)
            match = self._ROUTE_RE.search(text)
            if match:
                method = match.group(1).upper()
                path = match.group(2)
                endpoints.append(FactItem(
                    fact_type="endpoint",
                    value=f"{method} {path}",
                    file=file_path,
                    line=node.start_point.row + 1,
                    language="ruby",
                ))

        for child in node.children:
            self._walk_endpoints(child, file_path, endpoints)

    # ------------------------------------------------------------------
    # Schemas — ActiveRecord models
    # ------------------------------------------------------------------

    _AR_BASES = {"ApplicationRecord", "ActiveRecord::Base"}

    def _walk_schemas(self, node, file_path: str, schemas: list[ASTSymbol]) -> None:
        for child in node.children:
            if child.type == "class":
                superclass = self._get_superclass(child)
                if superclass and any(b in superclass for b in self._AR_BASES):
                    name_node = find_first_child(child, "constant", "scope_resolution")
                    if name_node:
                        name = node_text(name_node)
                        schemas.append(ASTSymbol(
                            name=name,
                            kind="schema",
                            signature=f"class {name} < {superclass}",
                            line=child.start_point.row + 1,
                            file=file_path,
                        ))

        for child in node.children:
            if child.type in ("class", "module"):
                body = find_first_child(child, "body_statement")
                if body:
                    self._walk_schemas(body, file_path, schemas)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_params(self, method_node) -> list[str]:
        """Parse method parameters."""
        params: list[str] = []
        params_node = find_first_child(method_node, "method_parameters")
        if not params_node:
            return params
        for child in params_node.children:
            if child.type in (
                "identifier", "optional_parameter", "keyword_parameter",
                "splat_parameter", "hash_splat_parameter",
                "block_parameter",
            ):
                params.append(node_text(child).strip())
        return params

    def _get_superclass(self, class_node) -> str:
        """Extract superclass from class < Base."""
        for child in class_node.children:
            if child.type == "superclass":
                # Remove the < prefix
                text = node_text(child).strip()
                if text.startswith("<"):
                    text = text[1:].strip()
                return text
        return ""

    def _get_comment(self, node) -> str | None:
        """Get comment preceding a node."""
        prev = node.prev_named_sibling
        if prev and prev.type == "comment":
            text = node_text(prev).lstrip("#").strip()
            return text if text else None
        return None
