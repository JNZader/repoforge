"""Lightweight extraction IR stubs.

These are cross-reference types for downstream changes — NOT
replacements for the full ``graph.Edge``, ``intelligence.ASTSymbol``,
or ``ripgrep.FactItem`` types.  They provide typed alternatives to
raw dicts when passing extraction results between pipeline stages.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class APIEndpoint:
    """A REST/HTTP endpoint discovered during extraction."""

    method: str
    """HTTP method: GET, POST, PUT, DELETE, etc."""

    path: str
    """Route path, e.g. /api/v1/users."""

    file: str
    """Source file where the endpoint is defined."""

    line: int
    """Line number in the source file."""

    handler: str = ""
    """Handler function/method name, if available."""

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "path": self.path,
            "file": self.file,
            "line": self.line,
            "handler": self.handler,
        }

    @classmethod
    def from_dict(cls, d: dict) -> APIEndpoint:
        return cls(
            method=d["method"],
            path=d["path"],
            file=d["file"],
            line=d.get("line", 0),
            handler=d.get("handler", ""),
        )


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    """A directed dependency between two modules.

    NOT a replacement for ``graph.Edge`` — this is a lightweight
    cross-reference for passing between pipeline stages.
    """

    source: str
    """Source module path."""

    target: str
    """Target module path."""

    kind: str = "imports"
    """Relationship kind: imports, depends_on, etc."""

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, d: dict) -> DependencyEdge:
        return cls(
            source=d["source"],
            target=d["target"],
            kind=d.get("kind", "imports"),
        )


@dataclass(frozen=True, slots=True)
class SymbolRef:
    """A lightweight cross-reference to a code symbol.

    NOT a replacement for ``intelligence.ASTSymbol`` — this is a
    minimal reference for passing between pipeline stages.
    """

    name: str
    """Symbol name (function, class, variable)."""

    file: str
    """Source file containing the symbol."""

    line: int
    """Line number in the source file."""

    kind: str = "function"
    """Symbol kind: function, class, variable, etc."""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "file": self.file,
            "line": self.line,
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SymbolRef:
        return cls(
            name=d["name"],
            file=d["file"],
            line=d.get("line", 0),
            kind=d.get("kind", "function"),
        )
