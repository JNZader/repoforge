"""
symbols — Symbol-level dependency graph extraction.

Regex-based parsing to extract function/class definitions and build
call graphs showing which symbols call which. Produces Mermaid diagrams
for symbol-level architecture documentation.
"""

from .extractor import Symbol, extract_symbols
from .graph import CallEdge, SymbolGraph, build_symbol_graph
from .renderer import render_symbol_mermaid

__all__ = [
    "CallEdge",
    "Symbol",
    "SymbolGraph",
    "build_symbol_graph",
    "extract_symbols",
    "render_symbol_mermaid",
]
