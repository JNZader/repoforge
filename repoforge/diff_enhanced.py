"""Enhanced entity-level diff with three improvements:

1. Method-level granularity — qualify methods as ClassName.method_name
2. In-memory diff — compare two strings without git
3. Diff + Impact composition — wire changes into EntityGraph for blast radius

Uses existing modules: symbols/extractor.py, diff.py, entity_impact.py.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from .entity_impact import Entity, EntityGraph, ImpactReport
from .symbols.extractor import Symbol, extract_symbols

# ── Types ──

@dataclass
class InMemoryDiffEntry:
    """A single entity change detected from in-memory comparison."""
    name: str
    kind: str
    status: str  # "added", "removed", "modified"
    file: str
    old_body: str = ""
    new_body: str = ""


@dataclass
class InMemoryDiffResult:
    """Result of an in-memory entity diff."""
    file: str
    entries: list[InMemoryDiffEntry] = field(default_factory=list)

    @property
    def added(self) -> list[InMemoryDiffEntry]:
        return [e for e in self.entries if e.status == "added"]

    @property
    def removed(self) -> list[InMemoryDiffEntry]:
        return [e for e in self.entries if e.status == "removed"]

    @property
    def modified(self) -> list[InMemoryDiffEntry]:
        return [e for e in self.entries if e.status == "modified"]


# ── Mejora 1: Method-level granularity ──

def qualify_method_names(
    symbols: list[Symbol], source_code: str,
) -> list[Symbol]:
    """Qualify function symbols that are inside a class with ClassName.method.

    Uses line number ranges: if a function's line is within a class's
    line range, it's a method.
    """
    # Find class ranges
    classes = [(s.name, s.line, s.end_line) for s in symbols if s.kind == "class"]
    if not classes:
        return symbols

    qualified: list[Symbol] = []
    for sym in symbols:
        if sym.kind == "function":
            # Check if inside any class range
            parent_class = None
            for cls_name, cls_start, cls_end in classes:
                if cls_start < sym.line <= cls_end:
                    parent_class = cls_name
                    break

            if parent_class:
                qualified.append(Symbol(
                    name=f"{parent_class}.{sym.name}",
                    kind="method",
                    file=sym.file,
                    line=sym.line,
                    end_line=sym.end_line,
                    params=sym.params,
                ))
            else:
                qualified.append(sym)
        else:
            qualified.append(sym)

    return qualified


# ── Mejora 2: In-memory diff ──

def _body_hash(source: str, sym: Symbol) -> str:
    """Hash the body of a symbol for change detection."""
    lines = source.split("\n")
    start = max(0, sym.line - 1)
    end = min(len(lines), sym.end_line)
    body = "\n".join(lines[start:end]).strip()
    # Normalize whitespace for cosmetic change tolerance
    normalized = " ".join(body.split())
    return hashlib.md5(normalized.encode()).hexdigest()


def diff_symbols_in_memory(
    old_source: str,
    new_source: str,
    language: str,
    file_path: str,
) -> InMemoryDiffResult:
    """Compare two versions of a file at the entity level in memory.

    No git required — works on raw strings.
    """
    old_symbols = extract_symbols(old_source, language, file_path)
    new_symbols = extract_symbols(new_source, language, file_path)

    # Qualify method names
    old_qualified = qualify_method_names(old_symbols, old_source)
    new_qualified = qualify_method_names(new_symbols, new_source)

    # Build name→symbol maps
    old_map: dict[str, Symbol] = {s.name: s for s in old_qualified}
    new_map: dict[str, Symbol] = {s.name: s for s in new_qualified}

    # Build body hashes
    old_hashes: dict[str, str] = {
        name: _body_hash(old_source, sym) for name, sym in old_map.items()
    }
    new_hashes: dict[str, str] = {
        name: _body_hash(new_source, sym) for name, sym in new_map.items()
    }

    entries: list[InMemoryDiffEntry] = []

    # Added: in new but not in old
    for name in new_map:
        if name not in old_map:
            entries.append(InMemoryDiffEntry(
                name=name, kind=new_map[name].kind, status="added", file=file_path,
            ))

    # Removed: in old but not in new
    for name in old_map:
        if name not in new_map:
            entries.append(InMemoryDiffEntry(
                name=name, kind=old_map[name].kind, status="removed", file=file_path,
            ))

    # Modified: in both but different body hash
    for name in old_map:
        if name in new_map:
            if old_hashes.get(name) != new_hashes.get(name):
                entries.append(InMemoryDiffEntry(
                    name=name, kind=new_map[name].kind, status="modified", file=file_path,
                ))

    return InMemoryDiffResult(file=file_path, entries=entries)


# ── Mejora 3: Diff + Impact composition ──

def diff_with_impact(
    old_source: str,
    new_source: str,
    language: str,
    file_path: str,
    graph: EntityGraph,
) -> list[ImpactReport]:
    """Diff two file versions and analyze impact of each modified entity.

    Returns an ImpactReport for each modified (not added/removed) entity,
    showing what other entities depend on it.
    """
    diff = diff_symbols_in_memory(old_source, new_source, language, file_path)
    impacts: list[ImpactReport] = []

    for entry in diff.modified:
        # Find entity in graph
        entity = graph.get_entity(file_path, entry.name)
        if not entity:
            # Try without class prefix
            short_name = entry.name.split(".")[-1]
            entity = graph.get_entity(file_path, short_name)

        if entity:
            impact = graph.analyze_impact(entity)
            impacts.append(impact)
        else:
            # Entity not in graph — create minimal report
            standalone = Entity(entry.name, file_path, 0, entry.kind)
            impacts.append(ImpactReport(target=standalone))

    return impacts
