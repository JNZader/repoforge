"""
deep_analysis.py — 5-layer analysis: AST + Call Graph + CFG + DFG + PDG.

Extends repoforge's analysis with deeper layers beyond the existing AST and
call graph:

  Layer 1: AST         — functions, classes, methods (existing infrastructure)
  Layer 2: Call Graph   — who calls whom (existing symbols.graph)
  Layer 3: CFG          — control flow: branches, loops, conditionals
  Layer 4: DFG          — data flow: variable definitions and uses
  Layer 5: PDG          — program dependence graph (CFG + DFG combined)

All layers use regex-based extraction (no tree-sitter required) and build
on the existing extractor and symbols infrastructure.

Entry points:
  - analyze_file(repo_path, file_path, depth=5) → FileAnalysis
  - analyze_repo(repo_path, depth=5, files=None) → RepoAnalysis
  - format_analysis(analysis) → human-readable markdown
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ASTNode:
    """A symbol from Layer 1 (AST)."""

    name: str
    kind: str  # function, class, method
    file: str
    line: int
    end_line: int
    params: list[str] = field(default_factory=list)


@dataclass
class CallEdgeInfo:
    """An edge from Layer 2 (Call Graph)."""

    caller: str
    callee: str
    file: str
    line: int


@dataclass
class CFGNode:
    """A control flow node from Layer 3 (CFG)."""

    node_type: str  # branch, loop, conditional, try, return
    label: str  # e.g., "if condition", "for item in items"
    file: str
    line: int
    parent_function: str
    depth: int = 0  # nesting depth


@dataclass
class DFGEdge:
    """A data flow edge from Layer 4 (DFG)."""

    variable: str
    definition_line: int
    use_line: int
    file: str
    parent_function: str
    flow_type: str = "def-use"  # def-use, def-def, use-use


@dataclass
class PDGEdge:
    """A program dependence edge from Layer 5 (PDG)."""

    source: str  # node description (e.g., "if condition L12")
    target: str  # node description (e.g., "x = compute() L14")
    dep_type: str  # control, data, both
    file: str


@dataclass
class FunctionAnalysis:
    """Complete multi-layer analysis for a single function."""

    name: str
    file: str
    line: int
    end_line: int
    params: list[str] = field(default_factory=list)

    # Layer 2: calls made from this function
    calls: list[CallEdgeInfo] = field(default_factory=list)

    # Layer 3: control flow nodes
    cfg_nodes: list[CFGNode] = field(default_factory=list)

    # Layer 4: data flow edges
    dfg_edges: list[DFGEdge] = field(default_factory=list)

    # Layer 5: PDG edges
    pdg_edges: list[PDGEdge] = field(default_factory=list)

    @property
    def cyclomatic_complexity(self) -> int:
        """Estimate cyclomatic complexity from CFG branch nodes."""
        return 1 + len(self.cfg_nodes)

    @property
    def complexity_rating(self) -> str:
        cc = self.cyclomatic_complexity
        if cc <= 5:
            return "low"
        if cc <= 10:
            return "moderate"
        if cc <= 20:
            return "high"
        return "very-high"


@dataclass
class FileAnalysis:
    """Multi-layer analysis for a single file."""

    file_path: str
    language: str
    depth: int  # how many layers were analyzed (1-5)

    # Layer 1: AST nodes
    ast_nodes: list[ASTNode] = field(default_factory=list)

    # Layer 2: Call edges
    call_edges: list[CallEdgeInfo] = field(default_factory=list)

    # Layer 3: CFG nodes
    cfg_nodes: list[CFGNode] = field(default_factory=list)

    # Layer 4: DFG edges
    dfg_edges: list[DFGEdge] = field(default_factory=list)

    # Layer 5: PDG edges
    pdg_edges: list[PDGEdge] = field(default_factory=list)

    # Per-function breakdown
    functions: list[FunctionAnalysis] = field(default_factory=list)

    @property
    def total_complexity(self) -> int:
        return sum(f.cyclomatic_complexity for f in self.functions) if self.functions else 0


@dataclass
class RepoAnalysis:
    """Aggregated multi-layer analysis for a repository."""

    repo_path: str
    depth: int
    files: list[FileAnalysis] = field(default_factory=list)

    @property
    def total_functions(self) -> int:
        return sum(len(f.ast_nodes) for f in self.files)

    @property
    def total_call_edges(self) -> int:
        return sum(len(f.call_edges) for f in self.files)

    @property
    def total_cfg_nodes(self) -> int:
        return sum(len(f.cfg_nodes) for f in self.files)

    @property
    def total_dfg_edges(self) -> int:
        return sum(len(f.dfg_edges) for f in self.files)

    @property
    def total_pdg_edges(self) -> int:
        return sum(len(f.pdg_edges) for f in self.files)

    @property
    def avg_complexity(self) -> float:
        funcs = [fn for fa in self.files for fn in fa.functions]
        if not funcs:
            return 0.0
        return sum(fn.cyclomatic_complexity for fn in funcs) / len(funcs)

    @property
    def hotspots(self) -> list[FunctionAnalysis]:
        """Functions with highest cyclomatic complexity (top 10)."""
        all_fns = [fn for fa in self.files for fn in fa.functions]
        return sorted(all_fns, key=lambda f: f.cyclomatic_complexity, reverse=True)[:10]


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

_LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
}


def _detect_language(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    return _LANG_MAP.get(ext, "")


# ---------------------------------------------------------------------------
# Layer 1: AST extraction (function/class definitions)
# ---------------------------------------------------------------------------

# Python
_PY_FUNC_RE = re.compile(
    r"^([ \t]*)(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)\s*(?:->.*?)?:", re.MULTILINE,
)
_PY_CLASS_RE = re.compile(
    r"^([ \t]*)class\s+(\w+)\s*(?:\([^)]*\))?\s*:", re.MULTILINE,
)

# TypeScript/JavaScript
_JS_FUNC_RE = re.compile(
    r"^[ \t]*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)",
    re.MULTILINE,
)
_JS_ARROW_RE = re.compile(
    r"^[ \t]*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*\w[^=]*)?\s*=>",
    re.MULTILINE,
)
_JS_CLASS_RE = re.compile(
    r"^[ \t]*(?:export\s+)?class\s+(\w+)", re.MULTILINE,
)

# Go
_GO_FUNC_RE = re.compile(
    r"^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(([^)]*)\)", re.MULTILINE,
)

# Java
_JAVA_METHOD_RE = re.compile(
    r"^[ \t]*(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)(\w+)\s*\(([^)]*)\)\s*(?:throws\s+\w+)?\s*\{",
    re.MULTILINE,
)
_JAVA_CLASS_RE = re.compile(
    r"^[ \t]*(?:public\s+)?(?:abstract\s+)?class\s+(\w+)", re.MULTILINE,
)

# Rust
_RUST_FN_RE = re.compile(
    r"^[ \t]*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)",
    re.MULTILINE,
)


def _get_block_end_python(lines: list[str], start_line: int) -> int:
    """Find end of Python block by indentation."""
    if start_line >= len(lines):
        return start_line
    def_line = lines[start_line]
    base_indent = len(def_line) - len(def_line.lstrip())
    end = start_line + 1
    while end < len(lines):
        line = lines[end]
        stripped = line.strip()
        if not stripped:
            end += 1
            continue
        if len(line) - len(line.lstrip()) <= base_indent:
            break
        end += 1
    return end


def _get_block_end_braces(lines: list[str], start_line: int) -> int:
    """Find end of brace-delimited block."""
    depth = 0
    found_open = False
    for i in range(start_line, len(lines)):
        for ch in lines[i]:
            if ch == "{":
                depth += 1
                found_open = True
            elif ch == "}":
                depth -= 1
                if found_open and depth == 0:
                    return i + 1
    return len(lines)


def _extract_ast_layer(content: str, file_path: str, lang: str) -> list[ASTNode]:
    """Extract Layer 1: AST symbols."""
    lines = content.split("\n")
    nodes: list[ASTNode] = []

    if lang == "python":
        for m in _PY_FUNC_RE.finditer(content):
            start = content[:m.start()].count("\n")
            end = _get_block_end_python(lines, start)
            params = [p.strip() for p in m.group(3).split(",") if p.strip()]
            nodes.append(ASTNode(
                name=m.group(2), kind="function", file=file_path,
                line=start + 1, end_line=end, params=params,
            ))
        for m in _PY_CLASS_RE.finditer(content):
            start = content[:m.start()].count("\n")
            end = _get_block_end_python(lines, start)
            nodes.append(ASTNode(
                name=m.group(2), kind="class", file=file_path,
                line=start + 1, end_line=end,
            ))

    elif lang in ("typescript", "javascript"):
        for m in _JS_FUNC_RE.finditer(content):
            start = content[:m.start()].count("\n")
            end = _get_block_end_braces(lines, start)
            params = [p.strip() for p in m.group(2).split(",") if p.strip()]
            nodes.append(ASTNode(
                name=m.group(1), kind="function", file=file_path,
                line=start + 1, end_line=end, params=params,
            ))
        for m in _JS_ARROW_RE.finditer(content):
            start = content[:m.start()].count("\n")
            end = _get_block_end_braces(lines, start)
            params = [p.strip() for p in m.group(2).split(",") if p.strip()]
            nodes.append(ASTNode(
                name=m.group(1), kind="function", file=file_path,
                line=start + 1, end_line=end, params=params,
            ))
        for m in _JS_CLASS_RE.finditer(content):
            start = content[:m.start()].count("\n")
            end = _get_block_end_braces(lines, start)
            nodes.append(ASTNode(
                name=m.group(1), kind="class", file=file_path,
                line=start + 1, end_line=end,
            ))

    elif lang == "go":
        for m in _GO_FUNC_RE.finditer(content):
            start = content[:m.start()].count("\n")
            end = _get_block_end_braces(lines, start)
            params = [p.strip() for p in m.group(2).split(",") if p.strip()]
            nodes.append(ASTNode(
                name=m.group(1), kind="function", file=file_path,
                line=start + 1, end_line=end, params=params,
            ))

    elif lang == "java":
        for m in _JAVA_METHOD_RE.finditer(content):
            start = content[:m.start()].count("\n")
            end = _get_block_end_braces(lines, start)
            params = [p.strip() for p in m.group(2).split(",") if p.strip()]
            nodes.append(ASTNode(
                name=m.group(1), kind="function", file=file_path,
                line=start + 1, end_line=end, params=params,
            ))
        for m in _JAVA_CLASS_RE.finditer(content):
            start = content[:m.start()].count("\n")
            end = _get_block_end_braces(lines, start)
            nodes.append(ASTNode(
                name=m.group(1), kind="class", file=file_path,
                line=start + 1, end_line=end,
            ))

    elif lang == "rust":
        for m in _RUST_FN_RE.finditer(content):
            start = content[:m.start()].count("\n")
            end = _get_block_end_braces(lines, start)
            params = [p.strip() for p in m.group(2).split(",") if p.strip()]
            nodes.append(ASTNode(
                name=m.group(1), kind="function", file=file_path,
                line=start + 1, end_line=end, params=params,
            ))

    return nodes


# ---------------------------------------------------------------------------
# Layer 2: Call graph extraction
# ---------------------------------------------------------------------------

# Matches function calls: name(
_CALL_RE = re.compile(r"\b(\w+)\s*\(")

# Names to skip (language keywords, builtins)
_SKIP_CALLS: set[str] = {
    "if", "for", "while", "return", "print", "len", "range", "str", "int",
    "float", "bool", "list", "dict", "set", "tuple", "type", "super",
    "isinstance", "issubclass", "hasattr", "getattr", "setattr", "delattr",
    "import", "from", "class", "def", "async", "await", "yield", "raise",
    "try", "except", "finally", "with", "as", "pass", "break", "continue",
    "lambda", "assert", "del", "in", "not", "and", "or", "is", "None",
    "True", "False", "self", "cls", "fmt", "func", "new", "make", "append",
    "extend", "pop", "keys", "values", "items", "get", "update",
    # Common exceptions/builtins
    "ValueError", "TypeError", "KeyError", "IndexError", "RuntimeError",
    "AttributeError", "OSError", "IOError", "FileNotFoundError",
    "NotImplementedError", "StopIteration", "Exception", "BaseException",
    "map", "filter", "sorted", "reversed", "enumerate", "zip", "any", "all",
    "min", "max", "sum", "abs", "round", "hash", "id", "repr", "open",
    "format", "input", "object", "property", "staticmethod", "classmethod",
    # Go
    "func", "var", "const", "package", "defer", "go", "select", "case",
    "switch", "fallthrough", "chan",
    # JS/TS
    "function", "const", "let", "var", "export", "require", "describe",
    "it", "test", "expect", "console", "log", "error", "warn",
}


def _extract_call_edges(
    content: str, file_path: str, ast_nodes: list[ASTNode],
) -> list[CallEdgeInfo]:
    """Extract Layer 2: function calls within each function body."""
    lines = content.split("\n")
    edges: list[CallEdgeInfo] = []
    known_names = {n.name for n in ast_nodes}

    for node in ast_nodes:
        if node.kind != "function":
            continue
        # Extract the function body
        body_start = node.line  # 1-indexed, so body starts after def line
        body_end = node.end_line
        body_lines = lines[body_start:body_end]
        body_text = "\n".join(body_lines)

        for m in _CALL_RE.finditer(body_text):
            callee = m.group(1)
            if callee in _SKIP_CALLS or callee == node.name:
                continue
            call_line = body_start + body_text[:m.start()].count("\n") + 1
            edges.append(CallEdgeInfo(
                caller=node.name,
                callee=callee,
                file=file_path,
                line=call_line,
            ))

    return edges


# ---------------------------------------------------------------------------
# Layer 3: Control flow graph (CFG)
# ---------------------------------------------------------------------------

# Python control flow
_PY_CFG_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^([ \t]*)if\s+(.+?)\s*:", re.MULTILINE), "branch"),
    (re.compile(r"^([ \t]*)elif\s+(.+?)\s*:", re.MULTILINE), "branch"),
    (re.compile(r"^([ \t]*)else\s*:", re.MULTILINE), "branch"),
    (re.compile(r"^([ \t]*)for\s+(.+?)\s+in\s+(.+?)\s*:", re.MULTILINE), "loop"),
    (re.compile(r"^([ \t]*)while\s+(.+?)\s*:", re.MULTILINE), "loop"),
    (re.compile(r"^([ \t]*)try\s*:", re.MULTILINE), "try"),
    (re.compile(r"^([ \t]*)except\s*(.*?)\s*:", re.MULTILINE), "try"),
    (re.compile(r"^([ \t]*)finally\s*:", re.MULTILINE), "try"),
    (re.compile(r"^([ \t]*)return\b(.*)", re.MULTILINE), "return"),
    (re.compile(r"^([ \t]*)raise\b(.*)", re.MULTILINE), "raise"),
]

# JS/TS control flow
_JS_CFG_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^([ \t]*)if\s*\((.+?)\)\s*\{", re.MULTILINE), "branch"),
    (re.compile(r"^([ \t]*)\}\s*else\s+if\s*\((.+?)\)\s*\{", re.MULTILINE), "branch"),
    (re.compile(r"^([ \t]*)\}\s*else\s*\{", re.MULTILINE), "branch"),
    (re.compile(r"^([ \t]*)for\s*\((.+?)\)\s*\{", re.MULTILINE), "loop"),
    (re.compile(r"^([ \t]*)while\s*\((.+?)\)\s*\{", re.MULTILINE), "loop"),
    (re.compile(r"^([ \t]*)switch\s*\((.+?)\)\s*\{", re.MULTILINE), "branch"),
    (re.compile(r"^([ \t]*)try\s*\{", re.MULTILINE), "try"),
    (re.compile(r"^([ \t]*)\}\s*catch\s*\((.+?)\)\s*\{", re.MULTILINE), "try"),
    (re.compile(r"^([ \t]*)return\b(.*)", re.MULTILINE), "return"),
    (re.compile(r"^([ \t]*)throw\b(.*)", re.MULTILINE), "raise"),
]

# Go control flow
_GO_CFG_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^([ \t]*)if\s+(.+?)\s*\{", re.MULTILINE), "branch"),
    (re.compile(r"^([ \t]*)\}\s*else\s+if\s+(.+?)\s*\{", re.MULTILINE), "branch"),
    (re.compile(r"^([ \t]*)\}\s*else\s*\{", re.MULTILINE), "branch"),
    (re.compile(r"^([ \t]*)for\s+(.*?)\s*\{", re.MULTILINE), "loop"),
    (re.compile(r"^([ \t]*)switch\s+(.*?)\s*\{", re.MULTILINE), "branch"),
    (re.compile(r"^([ \t]*)select\s*\{", re.MULTILINE), "branch"),
    (re.compile(r"^([ \t]*)return\b(.*)", re.MULTILINE), "return"),
    (re.compile(r"^([ \t]*)defer\b(.*)", re.MULTILINE), "try"),
]


def _get_cfg_patterns(lang: str) -> list[tuple[re.Pattern, str]]:
    if lang == "python":
        return _PY_CFG_PATTERNS
    if lang in ("typescript", "javascript"):
        return _JS_CFG_PATTERNS
    if lang == "go":
        return _GO_CFG_PATTERNS
    if lang in ("java", "rust"):
        return _JS_CFG_PATTERNS  # close enough for brace languages
    return []


def _extract_cfg_layer(
    content: str, file_path: str, lang: str, ast_nodes: list[ASTNode],
) -> list[CFGNode]:
    """Extract Layer 3: control flow nodes within each function."""
    lines = content.split("\n")
    cfg_nodes: list[CFGNode] = []
    patterns = _get_cfg_patterns(lang)

    if not patterns:
        return cfg_nodes

    for func_node in ast_nodes:
        if func_node.kind != "function":
            continue

        body_start = func_node.line - 1  # convert to 0-indexed
        body_end = func_node.end_line
        body_text = "\n".join(lines[body_start:body_end])

        for pattern, node_type in patterns:
            for m in pattern.finditer(body_text):
                indent = m.group(1)
                label_parts = m.groups()[1:]  # everything after indent
                label_text = " ".join(p.strip() for p in label_parts if p and p.strip())
                if not label_text:
                    label_text = node_type

                match_line = body_start + body_text[:m.start()].count("\n") + 1
                depth = len(indent) // 4 if indent else 0

                cfg_nodes.append(CFGNode(
                    node_type=node_type,
                    label=f"{node_type}: {label_text}"[:120],
                    file=file_path,
                    line=match_line,
                    parent_function=func_node.name,
                    depth=depth,
                ))

    return cfg_nodes


# ---------------------------------------------------------------------------
# Layer 4: Data flow graph (DFG)
# ---------------------------------------------------------------------------

# Python assignment: name = ...
_PY_ASSIGN_RE = re.compile(r"^([ \t]*)(\w+)\s*(?::\s*\w[^=]*)?\s*=(?!=)", re.MULTILINE)
# Python augmented assignment: name += ...
_PY_AUG_ASSIGN_RE = re.compile(r"^([ \t]*)(\w+)\s*[+\-*/|&^%]+=", re.MULTILINE)

# JS/TS/Go/Java/Rust: variable declaration or assignment
_BRACE_ASSIGN_RE = re.compile(
    r"^([ \t]*)(?:(?:let|const|var|auto|val)\s+)?(\w+)\s*(?::\s*\w[^=]*)?\s*=(?!=)",
    re.MULTILINE,
)

# Variable use: simple identifier reference (not in assignment position)
_VAR_USE_RE = re.compile(r"\b(\w+)\b")


def _extract_dfg_layer(
    content: str, file_path: str, lang: str, ast_nodes: list[ASTNode],
) -> list[DFGEdge]:
    """Extract Layer 4: variable def-use chains within each function."""
    lines = content.split("\n")
    edges: list[DFGEdge] = []

    assign_re = _PY_ASSIGN_RE if lang == "python" else _BRACE_ASSIGN_RE

    for func_node in ast_nodes:
        if func_node.kind != "function":
            continue

        body_start = func_node.line - 1
        body_end = func_node.end_line
        func_lines = lines[body_start:body_end]

        # Collect definitions: variable → list of line numbers
        definitions: dict[str, list[int]] = {}

        # Parameters are definitions at function start
        for param in func_node.params:
            # strip type annotations
            param_name = param.split(":")[0].split("=")[0].strip()
            param_name = param_name.lstrip("*")  # *args, **kwargs
            if param_name and param_name.isidentifier():
                definitions.setdefault(param_name, []).append(func_node.line)

        # Find assignments within function body
        body_text = "\n".join(func_lines)
        for m in assign_re.finditer(body_text):
            var_name = m.group(2)
            if var_name.startswith("_") and var_name != "_":
                continue  # skip private-ish vars for noise reduction
            if not var_name[0].islower():
                continue  # skip constants/classes
            def_line = body_start + body_text[:m.start()].count("\n") + 1
            definitions.setdefault(var_name, []).append(def_line)

        # Find uses and create def-use edges
        for line_idx, line_text in enumerate(func_lines):
            abs_line = body_start + line_idx + 1
            # Skip the line if it's a definition line
            for var_name, def_lines in definitions.items():
                if abs_line in def_lines:
                    continue
                if re.search(rf"\b{re.escape(var_name)}\b", line_text):
                    # Find the closest prior definition
                    prior_defs = [d for d in def_lines if d < abs_line]
                    if prior_defs:
                        edges.append(DFGEdge(
                            variable=var_name,
                            definition_line=prior_defs[-1],
                            use_line=abs_line,
                            file=file_path,
                            parent_function=func_node.name,
                        ))

    return edges


# ---------------------------------------------------------------------------
# Layer 5: Program dependence graph (PDG) — combines CFG + DFG
# ---------------------------------------------------------------------------


def _build_pdg_layer(
    cfg_nodes: list[CFGNode],
    dfg_edges: list[DFGEdge],
    file_path: str,
) -> list[PDGEdge]:
    """Build Layer 5: combine control flow and data flow into PDG edges."""
    pdg_edges: list[PDGEdge] = []

    # Index CFG nodes by line
    cfg_by_line: dict[int, CFGNode] = {}
    for node in cfg_nodes:
        cfg_by_line[node.line] = node

    # For each DFG edge, check if the def or use is under a CFG node
    for dfg in dfg_edges:
        # Check if the use is control-dependent on a branch
        control_dep: CFGNode | None = None
        for cfg in cfg_nodes:
            if cfg.parent_function == dfg.parent_function:
                if cfg.node_type in ("branch", "loop") and cfg.line <= dfg.use_line:
                    if control_dep is None or cfg.line > control_dep.line:
                        control_dep = cfg

        if control_dep:
            # Both control and data dependency
            pdg_edges.append(PDGEdge(
                source=f"{control_dep.node_type} L{control_dep.line}",
                target=f"{dfg.variable}={dfg.variable} L{dfg.use_line}",
                dep_type="both",
                file=file_path,
            ))
        else:
            # Pure data dependency
            pdg_edges.append(PDGEdge(
                source=f"def {dfg.variable} L{dfg.definition_line}",
                target=f"use {dfg.variable} L{dfg.use_line}",
                dep_type="data",
                file=file_path,
            ))

    # Add pure control dependencies (CFG nodes without associated DFG)
    dfg_lines = {e.use_line for e in dfg_edges} | {e.definition_line for e in dfg_edges}
    for cfg in cfg_nodes:
        if cfg.line not in dfg_lines and cfg.node_type in ("branch", "loop"):
            pdg_edges.append(PDGEdge(
                source=f"{cfg.node_type} L{cfg.line}",
                target=f"block after {cfg.node_type} L{cfg.line}",
                dep_type="control",
                file=file_path,
            ))

    return pdg_edges


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------


def analyze_file(
    repo_path: str,
    file_path: str,
    depth: int = 5,
) -> FileAnalysis:
    """Analyze a single file through up to 5 layers.

    Args:
        repo_path: Absolute path to the repository root.
        file_path: Relative file path within the repo.
        depth: Number of layers to analyze (1-5).

    Returns:
        FileAnalysis with results from each requested layer.
    """
    root = Path(repo_path).resolve()
    abs_path = root / file_path
    lang = _detect_language(file_path)

    if not lang:
        return FileAnalysis(file_path=file_path, language="", depth=0)

    try:
        content = abs_path.read_text(errors="replace")
    except OSError:
        logger.warning("Failed to read %s", abs_path)
        return FileAnalysis(file_path=file_path, language=lang, depth=0)

    result = FileAnalysis(file_path=file_path, language=lang, depth=min(depth, 5))

    # Layer 1: AST
    ast_nodes = _extract_ast_layer(content, file_path, lang)
    result.ast_nodes = ast_nodes

    # Layer 2: Call Graph
    call_edges: list[CallEdgeInfo] = []
    if depth >= 2:
        call_edges = _extract_call_edges(content, file_path, ast_nodes)
        result.call_edges = call_edges

    # Layer 3: CFG
    cfg_nodes: list[CFGNode] = []
    if depth >= 3:
        cfg_nodes = _extract_cfg_layer(content, file_path, lang, ast_nodes)
        result.cfg_nodes = cfg_nodes

    # Layer 4: DFG
    dfg_edges: list[DFGEdge] = []
    if depth >= 4:
        dfg_edges = _extract_dfg_layer(content, file_path, lang, ast_nodes)
        result.dfg_edges = dfg_edges

    # Layer 5: PDG
    pdg_edges: list[PDGEdge] = []
    if depth >= 5:
        pdg_edges = _build_pdg_layer(cfg_nodes, dfg_edges, file_path)
        result.pdg_edges = pdg_edges

    # Build per-function analysis (always, using whatever layers are available)
    for ast_node in ast_nodes:
        if ast_node.kind != "function":
            continue
        fn = FunctionAnalysis(
            name=ast_node.name,
            file=file_path,
            line=ast_node.line,
            end_line=ast_node.end_line,
            params=ast_node.params,
            calls=[e for e in call_edges if e.caller == ast_node.name],
            cfg_nodes=[n for n in cfg_nodes if n.parent_function == ast_node.name],
            dfg_edges=[e for e in dfg_edges if e.parent_function == ast_node.name],
            pdg_edges=[
                e for e in pdg_edges
                if any(
                    n.parent_function == ast_node.name
                    for n in cfg_nodes
                    if f"L{n.line}" in e.source
                )
                or any(
                    d.parent_function == ast_node.name
                    for d in dfg_edges
                    if f"L{d.use_line}" in e.target or f"L{d.definition_line}" in e.source
                )
            ],
        )
        result.functions.append(fn)

    return result


def analyze_repo(
    repo_path: str,
    depth: int = 5,
    files: list[str] | None = None,
) -> RepoAnalysis:
    """Analyze a repository through up to 5 layers.

    Args:
        repo_path: Absolute path to the repository root.
        depth: Number of layers to analyze (1-5).
        files: Optional list of relative file paths. If None, discovers files.

    Returns:
        RepoAnalysis with per-file results.
    """
    root = Path(repo_path).resolve()

    if files is None:
        from .ripgrep import list_files
        discovered = list_files(root)
        files = []
        for f in discovered:
            try:
                files.append(str(f.relative_to(root)))
            except ValueError:
                pass

    result = RepoAnalysis(repo_path=str(root), depth=depth)

    for file_path in files:
        lang = _detect_language(file_path)
        if not lang:
            continue
        fa = analyze_file(str(root), file_path, depth=depth)
        if fa.ast_nodes:  # Only include files with detected symbols
            result.files.append(fa)

    return result


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_analysis(analysis: RepoAnalysis | FileAnalysis) -> str:
    """Format analysis results as human-readable markdown."""
    if isinstance(analysis, FileAnalysis):
        return _format_file_analysis(analysis)
    return _format_repo_analysis(analysis)


def _format_file_analysis(fa: FileAnalysis) -> str:
    lines: list[str] = []
    lines.append(f"## File Analysis: `{fa.file_path}`")
    lines.append(f"**Language**: {fa.language}")
    lines.append(f"**Analysis depth**: {fa.depth}/5")
    lines.append("")

    if fa.ast_nodes:
        lines.append(f"### Layer 1: AST ({len(fa.ast_nodes)} symbols)")
        for n in fa.ast_nodes:
            lines.append(f"- {n.kind} **{n.name}** (L{n.line}-L{n.end_line})")
        lines.append("")

    if fa.call_edges:
        lines.append(f"### Layer 2: Call Graph ({len(fa.call_edges)} edges)")
        for e in fa.call_edges:
            lines.append(f"- `{e.caller}` -> `{e.callee}` (L{e.line})")
        lines.append("")

    if fa.cfg_nodes:
        lines.append(f"### Layer 3: CFG ({len(fa.cfg_nodes)} nodes)")
        for n in fa.cfg_nodes:
            indent = "  " * n.depth
            lines.append(f"- {indent}{n.label} (L{n.line}, fn:{n.parent_function})")
        lines.append("")

    if fa.dfg_edges:
        lines.append(f"### Layer 4: DFG ({len(fa.dfg_edges)} edges)")
        for e in fa.dfg_edges:
            lines.append(
                f"- `{e.variable}`: def L{e.definition_line} -> use L{e.use_line} "
                f"(fn:{e.parent_function})"
            )
        lines.append("")

    if fa.pdg_edges:
        lines.append(f"### Layer 5: PDG ({len(fa.pdg_edges)} edges)")
        for e in fa.pdg_edges:
            lines.append(f"- [{e.dep_type}] `{e.source}` -> `{e.target}`")
        lines.append("")

    if fa.functions:
        lines.append("### Function Complexity")
        for fn in sorted(fa.functions, key=lambda f: f.cyclomatic_complexity, reverse=True):
            lines.append(
                f"- **{fn.name}**: CC={fn.cyclomatic_complexity} ({fn.complexity_rating})"
            )
        lines.append("")

    return "\n".join(lines)


def _format_repo_analysis(ra: RepoAnalysis) -> str:
    lines: list[str] = []
    lines.append("## Repository Analysis")
    lines.append(f"**Analysis depth**: {ra.depth}/5")
    lines.append(f"**Files analyzed**: {len(ra.files)}")
    lines.append(f"**Total functions**: {ra.total_functions}")
    lines.append("")

    lines.append("### Layer Summary")
    lines.append(f"| Layer | Count |")
    lines.append(f"|-------|-------|")
    lines.append(f"| L1: AST symbols | {ra.total_functions} |")
    if ra.depth >= 2:
        lines.append(f"| L2: Call edges | {ra.total_call_edges} |")
    if ra.depth >= 3:
        lines.append(f"| L3: CFG nodes | {ra.total_cfg_nodes} |")
    if ra.depth >= 4:
        lines.append(f"| L4: DFG edges | {ra.total_dfg_edges} |")
    if ra.depth >= 5:
        lines.append(f"| L5: PDG edges | {ra.total_pdg_edges} |")
    lines.append("")

    lines.append(f"**Average complexity**: {ra.avg_complexity:.1f}")
    lines.append("")

    hotspots = ra.hotspots
    if hotspots:
        lines.append("### Complexity Hotspots")
        for fn in hotspots:
            lines.append(
                f"- **{fn.name}** (`{fn.file}:L{fn.line}`) "
                f"CC={fn.cyclomatic_complexity} ({fn.complexity_rating})"
            )
        lines.append("")

    return "\n".join(lines)


def analysis_to_json(analysis: RepoAnalysis | FileAnalysis) -> str:
    """Serialize analysis to JSON."""
    if isinstance(analysis, FileAnalysis):
        return _file_analysis_to_json(analysis)
    return _repo_analysis_to_json(analysis)


def _file_analysis_to_json(fa: FileAnalysis) -> str:
    data = {
        "file_path": fa.file_path,
        "language": fa.language,
        "depth": fa.depth,
        "ast_nodes": [
            {"name": n.name, "kind": n.kind, "line": n.line,
             "end_line": n.end_line, "params": n.params}
            for n in fa.ast_nodes
        ],
        "call_edges": [
            {"caller": e.caller, "callee": e.callee, "line": e.line}
            for e in fa.call_edges
        ],
        "cfg_nodes": [
            {"type": n.node_type, "label": n.label, "line": n.line,
             "parent_function": n.parent_function, "depth": n.depth}
            for n in fa.cfg_nodes
        ],
        "dfg_edges": [
            {"variable": e.variable, "def_line": e.definition_line,
             "use_line": e.use_line, "parent_function": e.parent_function}
            for e in fa.dfg_edges
        ],
        "pdg_edges": [
            {"source": e.source, "target": e.target, "dep_type": e.dep_type}
            for e in fa.pdg_edges
        ],
        "functions": [
            {"name": fn.name, "line": fn.line, "end_line": fn.end_line,
             "cyclomatic_complexity": fn.cyclomatic_complexity,
             "complexity_rating": fn.complexity_rating}
            for fn in fa.functions
        ],
    }
    return json.dumps(data, indent=2) + "\n"


def _repo_analysis_to_json(ra: RepoAnalysis) -> str:
    data = {
        "repo_path": ra.repo_path,
        "depth": ra.depth,
        "files_analyzed": len(ra.files),
        "total_functions": ra.total_functions,
        "total_call_edges": ra.total_call_edges,
        "total_cfg_nodes": ra.total_cfg_nodes,
        "total_dfg_edges": ra.total_dfg_edges,
        "total_pdg_edges": ra.total_pdg_edges,
        "avg_complexity": round(ra.avg_complexity, 2),
        "hotspots": [
            {"name": fn.name, "file": fn.file, "line": fn.line,
             "cyclomatic_complexity": fn.cyclomatic_complexity,
             "complexity_rating": fn.complexity_rating}
            for fn in ra.hotspots
        ],
        "files": [
            {
                "file_path": f.file_path,
                "language": f.language,
                "ast_count": len(f.ast_nodes),
                "call_count": len(f.call_edges),
                "cfg_count": len(f.cfg_nodes),
                "dfg_count": len(f.dfg_edges),
                "pdg_count": len(f.pdg_edges),
                "total_complexity": f.total_complexity,
            }
            for f in ra.files
        ],
    }
    return json.dumps(data, indent=2) + "\n"
