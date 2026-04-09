"""
C++ AST Extractor — tree-sitter based analysis for C++ source files.

Extracts functions, classes, structs, namespaces, methods, templates,
enums, and typedefs. Extends C patterns with class/namespace/template support.
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


class CppASTExtractor:
    """Tree-sitter based extractor for C++ files."""

    language_name: str = "cpp"
    file_extensions: list[str] = [".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".hh"]

    def __init__(self) -> None:
        self._parser = get_parser("cpp")

    def extract_symbols(self, content: str, file_path: str) -> list[ASTSymbol]:
        root = parse_source(self._parser, content)
        if root is None:
            return []

        symbols: list[ASTSymbol] = []
        self._walk_symbols(root, file_path, symbols)
        return symbols

    def extract_endpoints(self, content: str, file_path: str) -> list[FactItem]:
        # C++ rarely has web endpoints in the conventional sense
        return []

    def extract_schemas(self, content: str, file_path: str) -> list[ASTSymbol]:
        """Extract SQL CREATE TABLE from string literals."""
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
            elif child.type == "class_specifier":
                sym = self._extract_class(child, file_path)
                if sym:
                    symbols.append(sym)
                body = find_first_child(child, "field_declaration_list")
                if body:
                    self._extract_class_members(body, file_path, symbols)
            elif child.type == "struct_specifier":
                sym = self._extract_struct(child, file_path)
                if sym:
                    symbols.append(sym)
                body = find_first_child(child, "field_declaration_list")
                if body:
                    self._extract_class_members(body, file_path, symbols)
            elif child.type == "namespace_definition":
                body = find_first_child(child, "declaration_list")
                if body:
                    self._walk_symbols(body, file_path, symbols)
            elif child.type == "enum_specifier":
                sym = self._extract_enum(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "template_declaration":
                # Template wraps another declaration
                self._extract_template(child, file_path, symbols)
            elif child.type == "type_definition":
                sym = self._extract_typedef(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "declaration":
                syms = self._extract_declaration(child, file_path)
                symbols.extend(syms)

    def _extract_function(self, node, file_path: str) -> ASTSymbol | None:
        """Extract a function/method definition."""
        declarator = find_first_child(node, "function_declarator")
        if not declarator:
            # Try pointer_declarator -> function_declarator
            ptr_decl = find_first_child(node, "pointer_declarator")
            if ptr_decl:
                declarator = find_first_child(ptr_decl, "function_declarator")
            # Or reference_declarator
            ref_decl = find_first_child(node, "reference_declarator")
            if ref_decl:
                declarator = find_first_child(ref_decl, "function_declarator")
            if not declarator:
                return None

        name_node = (
            find_first_child(declarator, "identifier")
            or find_first_child(declarator, "qualified_identifier")
            or find_first_child(declarator, "field_identifier")
        )
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

    def _extract_class(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "type_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        bases = self._get_base_classes(node)
        fields = self._get_fields(node)
        comment = self._get_preceding_comment(node)

        sig = f"class {name}"
        if bases:
            sig += f" : {', '.join(bases)}"

        return ASTSymbol(
            name=name,
            kind="class",
            signature=sig,
            fields=fields,
            docstring=comment,
            line=node.start_point.row + 1,
            file=file_path,
        )

    def _extract_struct(self, node, file_path: str) -> ASTSymbol | None:
        name_node = find_first_child(node, "type_identifier")
        if not name_node:
            return None

        name = node_text(name_node)
        fields = self._get_fields(node)
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

    def _extract_template(
        self, node, file_path: str, symbols: list[ASTSymbol]
    ) -> None:
        """Extract template declarations (class/function)."""
        for child in node.children:
            if child.type == "class_specifier":
                sym = self._extract_class(child, file_path)
                if sym:
                    symbols.append(sym)
                body = find_first_child(child, "field_declaration_list")
                if body:
                    self._extract_class_members(body, file_path, symbols)
            elif child.type == "function_definition":
                sym = self._extract_function(child, file_path)
                if sym:
                    symbols.append(sym)
            elif child.type == "struct_specifier":
                sym = self._extract_struct(child, file_path)
                if sym:
                    symbols.append(sym)

    def _extract_typedef(self, node, file_path: str) -> ASTSymbol | None:
        text = node_text(node).strip().rstrip(";")
        name_node = find_first_child(node, "type_identifier")
        if not name_node:
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

    def _extract_declaration(self, node, file_path: str) -> list[ASTSymbol]:
        """Handle top-level declarations that might contain function prototypes."""
        symbols: list[ASTSymbol] = []
        func_decl = find_first_child(node, "function_declarator")
        if func_decl:
            name_node = (
                find_first_child(func_decl, "identifier")
                or find_first_child(func_decl, "qualified_identifier")
            )
            if name_node:
                name = node_text(name_node)
                params = self._parse_params(func_decl)
                ret = self._get_return_type(node)
                sig = f"{ret} {name}({', '.join(params)})" if ret else f"{name}({', '.join(params)})"
                symbols.append(ASTSymbol(
                    name=name,
                    kind="function",
                    signature=sig,
                    params=params,
                    return_type=ret,
                    line=node.start_point.row + 1,
                    file=file_path,
                ))
        return symbols

    def _extract_class_members(
        self, body_node, file_path: str, symbols: list[ASTSymbol]
    ) -> None:
        """Extract methods from class/struct body (field_declaration_list)."""
        for child in body_node.children:
            if child.type == "function_definition":
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
            elif child.type == "declaration":
                # Could be a method declaration (no body)
                func_decl = find_first_child(child, "function_declarator")
                if func_decl:
                    name_node = (
                        find_first_child(func_decl, "identifier")
                        or find_first_child(func_decl, "field_identifier")
                    )
                    if name_node:
                        name = node_text(name_node)
                        params = self._parse_params(func_decl)
                        ret = self._get_return_type(child)
                        sig = f"{ret} {name}({', '.join(params)})" if ret else f"{name}({', '.join(params)})"
                        symbols.append(ASTSymbol(
                            name=name,
                            kind="method",
                            signature=sig,
                            params=params,
                            return_type=ret,
                            line=child.start_point.row + 1,
                            file=file_path,
                        ))
            elif child.type == "access_specifier":
                pass  # public:, private:, protected:

    # ------------------------------------------------------------------
    # Schemas — SQL in string literals
    # ------------------------------------------------------------------

    _CREATE_TABLE_RE = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?",
        re.IGNORECASE,
    )

    def _walk_schemas(self, node, file_path: str, schemas: list[ASTSymbol]) -> None:
        if node.type in ("string_literal", "raw_string_literal"):
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
            if child.type in ("parameter_declaration", "optional_parameter_declaration"):
                params.append(node_text(child).strip())
        return params

    def _get_return_type(self, func_node) -> str | None:
        """Extract return type from function definition."""
        for child in func_node.children:
            if child.type in (
                "primitive_type", "type_identifier", "sized_type_specifier",
                "template_type", "auto", "qualified_identifier",
                "dependent_type",
            ):
                return node_text(child).strip()
            if child.type == "type_qualifier":
                next_sib = child.next_named_sibling
                if next_sib and next_sib.type in (
                    "primitive_type", "type_identifier", "template_type",
                ):
                    return f"{node_text(child)} {node_text(next_sib)}".strip()
        return None

    def _get_base_classes(self, node) -> list[str]:
        """Extract base class list from class/struct."""
        bases: list[str] = []
        for child in node.children:
            if child.type == "base_class_clause":
                text = node_text(child).lstrip(":").strip()
                bases = [b.strip() for b in text.split(",") if b.strip()]
                break
        return bases

    def _get_fields(self, node) -> list[str]:
        """Extract field declarations from class/struct body."""
        fields: list[str] = []
        body = find_first_child(node, "field_declaration_list")
        if not body:
            return fields
        for child in body.children:
            if child.type == "field_declaration":
                text = node_text(child).strip().rstrip(";")
                fields.append(text)
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
        """Get comment preceding a node."""
        prev = node.prev_named_sibling
        if prev and prev.type == "comment":
            text = node_text(prev)
            text = text.lstrip("/").lstrip("*").strip().rstrip("*/").strip()
            first_line = text.split("\n")[0].strip()
            return first_line if first_line else None
        return None
