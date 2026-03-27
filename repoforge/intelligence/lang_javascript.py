"""
JavaScript AST Extractor — tree-sitter based analysis for JavaScript source files.

Reuses TypeScript extractor logic where possible (similar AST structure).
Handles CommonJS require/module.exports and ES modules.
"""

from __future__ import annotations

from ..facts import FactItem
from .ast_extractor import (
    ASTSymbol,
    find_children,
    find_first_child,
    get_parser,
    node_text,
    parse_source,
)
from .lang_typescript import TypeScriptASTExtractor


class JavaScriptASTExtractor:
    """Tree-sitter based extractor for JavaScript files.

    Delegates most logic to TypeScriptASTExtractor methods but uses
    the JavaScript parser (no type annotations in the AST).
    """

    language_name: str = "javascript"
    file_extensions: list[str] = [".js", ".jsx", ".mjs", ".cjs"]

    def __init__(self) -> None:
        self._parser = get_parser("javascript")
        # Reuse TS extractor for shared logic
        self._ts = TypeScriptASTExtractor()

    def extract_symbols(self, content: str, file_path: str) -> list[ASTSymbol]:
        root = parse_source(self._parser, content)
        if root is None:
            return []

        symbols: list[ASTSymbol] = []
        for child in root.children:
            if child.type == "export_statement":
                self._ts._extract_export(child, file_path, symbols)
            elif child.type == "function_declaration":
                sym = self._ts._extract_function(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "class_declaration":
                sym = self._ts._extract_class(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "lexical_declaration":
                syms = self._ts._extract_const(child, file_path)
                symbols.extend(syms)
            # CommonJS: module.exports = { ... } or module.exports = ClassName
            elif child.type == "expression_statement":
                self._check_module_exports(child, file_path, symbols)

        return symbols

    def extract_endpoints(self, content: str, file_path: str) -> list[FactItem]:
        root = parse_source(self._parser, content)
        if root is None:
            return []

        endpoints: list[FactItem] = []
        self._ts._walk_endpoints(root, file_path, endpoints)
        return endpoints

    def extract_schemas(self, content: str, file_path: str) -> list[ASTSymbol]:
        root = parse_source(self._parser, content)
        if root is None:
            return []

        schemas: list[ASTSymbol] = []
        self._ts._walk_schemas(root, file_path, schemas)
        return schemas

    # ------------------------------------------------------------------
    # CommonJS module.exports
    # ------------------------------------------------------------------

    def _check_module_exports(
        self, node, file_path: str, symbols: list[ASTSymbol]
    ) -> None:
        """Detect module.exports = X patterns."""
        text = node_text(node)
        if "module.exports" not in text:
            return

        # module.exports = { key1, key2 }
        assignment = find_first_child(node, "assignment_expression")
        if not assignment:
            return

        right = None
        children = list(assignment.children)
        for i, c in enumerate(children):
            if c.type == "=" and i + 1 < len(children):
                right = children[i + 1]
                break

        if not right:
            return

        if right.type == "object":
            # module.exports = { fn1, fn2, Cls }
            for prop in find_children(right, "shorthand_property_identifier"):
                name = node_text(prop).strip()
                if name:
                    symbols.append(ASTSymbol(
                        name=name,
                        kind="variable",
                        signature=f"module.exports.{name}",
                        line=node.start_point.row + 1,
                        file=file_path,
                    ))
        elif right.type == "identifier":
            name = node_text(right).strip()
            if name:
                symbols.append(ASTSymbol(
                    name=name,
                    kind="variable",
                    signature=f"module.exports = {name}",
                    line=node.start_point.row + 1,
                    file=file_path,
                ))
