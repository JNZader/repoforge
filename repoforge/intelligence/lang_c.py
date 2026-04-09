"""
C AST Extractor — tree-sitter based analysis for C source files.

Extracts functions (with params + return types), structs, enums, typedefs,
and macro-defined constants. C has no endpoints/schemas in the web sense,
but we detect SQL patterns in string literals.
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


class CASTExtractor:
    """Tree-sitter based extractor for C files."""

    language_name: str = "c"
    file_extensions: list[str] = [".c", ".h"]

    def __init__(self) -> None:
        self._parser = get_parser("c")

    def extract_symbols(self, content: str, file_path: str) -> list[ASTSymbol]:
        root = parse_source(self._parser, content)
        if root is None:
            return []

        symbols: list[ASTSymbol] = []
        self._walk_symbols(root, file_path, symbols)
        return symbols

    def extract_endpoints(self, content: str, file_path: str) -> list[FactItem]:
        # C typically doesn't have web endpoints
        return []

    def extract_schemas(self, content: str, file_path: str) -> list[ASTSymbol]:
        """Extract SQL CREATE TABLE patterns from string literals."""
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
            elif child.type == "declaration":
                # Could be function declaration, struct, typedef, or variable
                syms = self._extract_declaration(child, file_path)
                symbols.extend(syms)
            elif child.type == "struct_specifier":
                sym = self._extract_struct(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "enum_specifier":
                sym = self._extract_enum(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "type_definition":
                sym = self._extract_typedef(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "preproc_def":
                sym = self._extract_macro(child, file_path)
                if sym:
                    symbols.append(sym)

    def _extract_function(self, node, file_path: str) -> ASTSymbol | None:
        """Extract a function definition."""
        # Get the declarator which contains function name and params
        declarator = find_first_child(node, "function_declarator")
        if not declarator:
            # Try nested in pointer_declarator
            ptr_decl = find_first_child(node, "pointer_declarator")
            if ptr_decl:
                declarator = find_first_child(ptr_decl, "function_declarator")
            if not declarator:
                return None

        name_node = find_first_child(declarator, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        params = self._parse_params(declarator)
        ret = self._get_return_type(node)
        comment = self._get_preceding_comment(node)

        sig = f"{ret} {name}({', '.join(params)})" if ret else f"{name}({', '.join(params)})"

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

    def _extract_declaration(self, node, file_path: str) -> list[ASTSymbol]:
        """Extract symbols from a declaration (function prototypes, struct defs, etc.)."""
        symbols: list[ASTSymbol] = []

        # Check for struct definition inside declaration
        for child in node.children:
            if child.type == "struct_specifier":
                sym = self._extract_struct(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "enum_specifier":
                sym = self._extract_enum(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "type_definition":
                sym = self._extract_typedef(child, file_path)
                if sym:
                    symbols.append(sym)

        # Check for function prototype
        func_decl = find_first_child(node, "function_declarator")
        if func_decl:
            name_node = find_first_child(func_decl, "identifier")
            if name_node:
                name = node_text(name_node)
                params = self._parse_params(func_decl)
                ret = self._get_return_type(node)
                comment = self._get_preceding_comment(node)

                sig = f"{ret} {name}({', '.join(params)})" if ret else f"{name}({', '.join(params)})"
                symbols.append(ASTSymbol(
                    name=name,
                    kind="function",
                    signature=sig,
                    params=params,
                    return_type=ret,
                    docstring=comment,
                    line=node.start_point.row + 1,
                    file=file_path,
                ))

        return symbols

    def _extract_struct(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "type_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        fields = self._parse_struct_fields(node)
        comment = self._get_preceding_comment(node)

        return ASTSymbol(
            name=name,
            kind="struct",
            signature=f"struct {name}",
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
        variants = self._parse_enum_values(node)
        comment = self._get_preceding_comment(node)

        return ASTSymbol(
            name=name,
            kind="type",
            signature=f"enum {name}",
            fields=variants,
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_typedef(self, node, file_path: str) -> ASTSymbol | None:
        """Extract typedef definitions."""
        # Get the typedef name (last identifier or type_identifier)
        text = node_text(node).strip().rstrip(";")
        # typedef ... Name;
        name_node = find_first_child(node, "type_identifier")
        if not name_node:
            # Fall back to any identifier at the end
            idents = find_children(node, "type_identifier", "identifier")
            if idents:
                name_node = idents[-1]
        if not name_node:
            return None

        name = node_text(name_node)

        return ASTSymbol(
            name=name,
            kind="type",
            signature=f"typedef {text.replace('typedef ', '')}",
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_macro(self, node, file_path: str) -> ASTSymbol | None:
        """Extract #define macros as constants."""
        name_node = find_first_child(node, "identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        # Only uppercase macros (convention for constants)
        if not name.isupper() and not name.startswith("__"):
            return None

        text = node_text(node).strip()
        return ASTSymbol(
            name=name,
            kind="constant",
            signature=text,
            line=node.start_point.row + 1,
            file=file_path,
        )

    # ------------------------------------------------------------------
    # Schemas — SQL in string literals
    # ------------------------------------------------------------------

    _CREATE_TABLE_RE = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?",
        re.IGNORECASE,
    )

    def _walk_schemas(self, node, file_path: str, schemas: list[ASTSymbol]) -> None:
        if node.type == "string_literal":
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
            self._walk_schemas(child, file_path, schemas)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_params(self, func_declarator) -> list[str]:
        """Parse function parameters."""
        params: list[str] = []
        param_list = find_first_child(func_declarator, "parameter_list")
        if not param_list:
            return params
        for child in param_list.children:
            if child.type == "parameter_declaration":
                params.append(node_text(child).strip())
        return params

    def _get_return_type(self, func_node) -> str | None:
        """Extract return type from function definition/declaration."""
        # Return type is typically a type specifier before the declarator
        for child in func_node.children:
            if child.type in (
                "primitive_type", "type_identifier", "sized_type_specifier",
                "struct_specifier", "enum_specifier",
            ):
                return node_text(child).strip()
            if child.type == "type_qualifier":
                # const int, etc. — need to combine with next type
                next_sib = child.next_named_sibling
                if next_sib and next_sib.type in (
                    "primitive_type", "type_identifier",
                ):
                    return f"{node_text(child)} {node_text(next_sib)}".strip()
        return None

    def _parse_struct_fields(self, struct_node) -> list[str]:
        """Extract struct field declarations."""
        fields: list[str] = []
        body = find_first_child(struct_node, "field_declaration_list")
        if not body:
            return fields
        for child in body.children:
            if child.type == "field_declaration":
                fields.append(node_text(child).strip().rstrip(";"))
        return fields

    def _parse_enum_values(self, enum_node) -> list[str]:
        """Extract enum constant names."""
        values: list[str] = []
        body = find_first_child(enum_node, "enumerator_list")
        if not body:
            return values
        for child in body.children:
            if child.type == "enumerator":
                values.append(node_text(child).strip().rstrip(","))
        return values

    def _get_preceding_comment(self, node) -> str | None:
        """Get comment block preceding a node."""
        prev = node.prev_named_sibling
        if prev and prev.type == "comment":
            text = node_text(prev)
            # Handle /* */ and // comments
            text = text.lstrip("/").lstrip("*").strip().rstrip("*/").strip()
            first_line = text.split("\n")[0].strip()
            return first_line if first_line else None
        return None
