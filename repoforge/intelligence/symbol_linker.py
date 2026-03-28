"""Cross-file symbol linking — resolves types, inheritance, and usages across files.

Given a dict[str, list[ASTSymbol]] (file → symbols), the SymbolLinker builds
an index that answers questions like:
- "Where is type X defined?" (resolve_type)
- "What does class Y inherit from?" (get_parents)
- "Who implements interface Z?" (get_implementors)
- "Which functions use type X in their signature?" (get_usages)
- "Give me the full context for type X" (format_type_context)

This powers richer documentation by connecting cross-file relationships
that individual extractors cannot see.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from .ast_extractor import ASTSymbol

logger = logging.getLogger(__name__)

# Kinds that represent type definitions (prioritized for resolve_type)
_TYPE_KINDS = ("class", "struct", "interface", "type", "enum", "trait", "schema")
_EXTENDS_RE = re.compile(r"\bextends\s+([\w.,\s]+)")
_IMPLEMENTS_RE = re.compile(r"\bimplements\s+([\w.,\s]+)")
_PARENS_RE = re.compile(r"^class\s+\w+\(([^)]+)\)")


class SymbolLinker:
    """Cross-file type resolution and relationship tracking."""

    def __init__(self, ast_symbols: dict[str, list[ASTSymbol]]) -> None:
        self._symbols = ast_symbols
        self._type_index: dict[str, ASTSymbol] = {}
        self._all_symbols: list[ASTSymbol] = []
        self._build_index()

    def _build_index(self) -> None:
        """Build name → symbol index, prioritizing type definitions."""
        for file_symbols in self._symbols.values():
            for sym in file_symbols:
                self._all_symbols.append(sym)
                existing = self._type_index.get(sym.name)
                if existing is None:
                    self._type_index[sym.name] = sym
                elif sym.kind in _TYPE_KINDS and existing.kind not in _TYPE_KINDS:
                    # Type definitions win over functions/variables with same name
                    self._type_index[sym.name] = sym

    def resolve_type(self, type_name: str) -> Optional[ASTSymbol]:
        """Find the definition of a type by name. Returns None if not found."""
        return self._type_index.get(type_name)

    def get_parents(self, class_name: str) -> list[str]:
        """Extract parent classes/interfaces from a class's signature.

        Parses extends/implements clauses and Python-style parenthetical
        inheritance from the signature string.
        """
        sym = self._type_index.get(class_name)
        if sym is None:
            return []

        sig = sym.signature
        parents: list[str] = []

        # Python-style: class Child(Base, Mixin)
        m = _PARENS_RE.match(sig)
        if m:
            parents.extend(
                p.strip() for p in m.group(1).split(",") if p.strip()
            )
            return parents

        # Java/TS-style: extends X implements Y, Z
        m = _EXTENDS_RE.search(sig)
        if m:
            parents.extend(
                p.strip() for p in m.group(1).split(",") if p.strip()
            )
        m = _IMPLEMENTS_RE.search(sig)
        if m:
            parents.extend(
                p.strip() for p in m.group(1).split(",") if p.strip()
            )

        return parents

    def get_implementors(self, interface_name: str) -> list[ASTSymbol]:
        """Find all symbols that extend/implement a given interface or class."""
        results = []
        for sym in self._all_symbols:
            if sym.kind not in _TYPE_KINDS:
                continue
            parents = self.get_parents(sym.name)
            if interface_name in parents:
                results.append(sym)
        return results

    def get_usages(self, type_name: str) -> list[ASTSymbol]:
        """Find symbols that reference a type in params, return type, or fields."""
        results = []
        for sym in self._all_symbols:
            if sym.name == type_name:
                continue
            # Check params
            if any(type_name in p for p in sym.params):
                results.append(sym)
                continue
            # Check return type
            if sym.return_type and type_name in sym.return_type:
                results.append(sym)
                continue
            # Check signature as fallback
            if type_name in sym.signature and sym.kind not in _TYPE_KINDS:
                results.append(sym)

        return results

    def format_type_context(self, type_name: str) -> str:
        """Format a rich context string for a type, including definition,
        inheritance chain, implementors, and usages.

        Returns empty string if the type is not found.
        """
        sym = self.resolve_type(type_name)
        if sym is None:
            return ""

        lines = [f"### {sym.name} ({sym.kind}, {sym.file}:{sym.line})"]
        lines.append(f"Signature: `{sym.signature}`")

        if sym.fields:
            lines.append(f"Fields: {', '.join(sym.fields[:8])}")

        # Inheritance
        parents = self.get_parents(type_name)
        if parents:
            parent_details = []
            for p in parents:
                parent_sym = self.resolve_type(p)
                if parent_sym:
                    parent_details.append(f"{p} ({parent_sym.file}:{parent_sym.line})")
                else:
                    parent_details.append(f"{p} (external)")
            lines.append(f"Inherits: {', '.join(parent_details)}")

        # Implementors
        impls = self.get_implementors(type_name)
        if impls:
            impl_names = [f"{s.name} ({s.file})" for s in impls[:5]]
            lines.append(f"Implemented by: {', '.join(impl_names)}")

        # Usages
        usages = self.get_usages(type_name)
        if usages:
            usage_names = [f"{s.name} ({s.file})" for s in usages[:5]]
            lines.append(f"Used by: {', '.join(usage_names)}")

        return "\n".join(lines)
