"""Advanced code analysis — dead code detection, complexity, example extraction.

All functions are deterministic (no LLM). They operate on AST symbols
and/or raw source code to produce structured reports.

Usage:
    from repoforge.analysis import detect_dead_code, analyze_complexity
    dead = detect_dead_code(ast_symbols)
    complexity = analyze_complexity(file_contents)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .intelligence.ast_extractor import ASTSymbol

logger = logging.getLogger(__name__)

# Names that are conventional entry points — never flag as dead
_ENTRY_POINT_NAMES = {"main", "setup", "app", "cli", "__init__", "run", "start"}
# Files that are entry points by convention
_ENTRY_POINT_FILES = {"main.py", "__init__.py", "cli.py", "app.py", "index.ts",
                       "index.js", "main.go", "main.rs", "Main.java"}
# Kinds that are often used externally (imports, type hints) — don't flag
_SAFE_KINDS = {"class", "struct", "interface", "type", "enum", "trait", "schema",
               "constant", "variable"}


# ---------------------------------------------------------------------------
# Dead code detection
# ---------------------------------------------------------------------------


@dataclass
class DeadCodeReport:
    """Report of potentially unused code."""
    unreferenced: list[ASTSymbol] = field(default_factory=list)
    total_symbols: int = 0
    analysis_scope: int = 0  # number of files analyzed


def detect_dead_code(ast_symbols: dict[str, list[ASTSymbol]]) -> DeadCodeReport:
    """Find functions that are never referenced by other symbols.

    Only flags functions — classes, types, and constants are excluded
    because they're often used via imports or type hints not visible
    in signatures alone.
    """
    if not ast_symbols:
        return DeadCodeReport()

    # Build reference index: collect all names referenced in signatures
    all_signatures = []
    all_symbols = []
    for file_syms in ast_symbols.values():
        for sym in file_syms:
            all_symbols.append(sym)
            all_signatures.append(sym.signature)

    combined_text = " ".join(all_signatures)

    # Check each function — is its name referenced by ANY other symbol?
    unreferenced = []
    for sym in all_symbols:
        if sym.kind in _SAFE_KINDS:
            continue
        if sym.kind != "function":
            continue
        if sym.name in _ENTRY_POINT_NAMES:
            continue
        if any(sym.file.endswith(ep) for ep in _ENTRY_POINT_FILES):
            continue
        if sym.name.startswith("_"):
            continue  # Private functions — skip

        # Count references in other symbols' signatures (exclude self)
        ref_count = combined_text.count(sym.name) - 1  # subtract self
        if ref_count <= 0:
            unreferenced.append(sym)

    return DeadCodeReport(
        unreferenced=unreferenced,
        total_symbols=len(all_symbols),
        analysis_scope=len(ast_symbols),
    )


# ---------------------------------------------------------------------------
# Complexity analysis
# ---------------------------------------------------------------------------


@dataclass
class ModuleComplexity:
    """Complexity metrics for a single file."""
    file: str
    avg_complexity: float
    max_complexity: float = 0.0
    function_count: int = 0
    most_complex: str = ""


@dataclass
class ComplexityReport:
    """Complexity analysis across all files."""
    modules: list[ModuleComplexity] = field(default_factory=list)


def analyze_complexity(file_contents: dict[str, str]) -> ComplexityReport:
    """Analyze cyclomatic complexity of source files.

    Uses a simple heuristic: count branching keywords (if, elif, else,
    for, while, except, and, or, case) as a proxy for cyclomatic complexity.
    No AST needed — works on raw source.
    """
    if not file_contents:
        return ComplexityReport()

    modules = []
    for filepath, content in file_contents.items():
        mc = _analyze_file(filepath, content)
        if mc:
            modules.append(mc)

    modules.sort(key=lambda m: m.avg_complexity, reverse=True)
    return ComplexityReport(modules=modules)


_BRANCH_PATTERN = re.compile(
    r"\b(if|elif|else|for|while|except|and|or|case|catch|switch)\b"
)
_FUNCTION_PATTERN = re.compile(
    r"^\s*(?:def|func|function|fn|pub fn|async def|async function)\s+(\w+)",
    re.MULTILINE,
)


def _analyze_file(filepath: str, content: str) -> ModuleComplexity | None:
    functions = _FUNCTION_PATTERN.findall(content)
    if not functions:
        # Count overall complexity even without function boundaries
        branches = len(_BRANCH_PATTERN.findall(content))
        if branches == 0:
            return ModuleComplexity(file=filepath, avg_complexity=1.0, function_count=0)
        return ModuleComplexity(
            file=filepath, avg_complexity=float(branches),
            function_count=0, max_complexity=float(branches),
        )

    # Split by function boundaries and count branches per function
    complexities: dict[str, int] = {}
    lines = content.split("\n")
    current_fn = None
    current_branches = 0

    for line in lines:
        fn_match = _FUNCTION_PATTERN.match(line)
        if fn_match:
            if current_fn:
                complexities[current_fn] = current_branches + 1  # +1 base
            current_fn = fn_match.group(1)
            current_branches = 0
        else:
            current_branches += len(_BRANCH_PATTERN.findall(line))

    if current_fn:
        complexities[current_fn] = current_branches + 1

    if not complexities:
        return None

    values = list(complexities.values())
    max_fn = max(complexities, key=complexities.get)

    return ModuleComplexity(
        file=filepath,
        avg_complexity=round(sum(values) / len(values), 1),
        max_complexity=float(max(values)),
        function_count=len(complexities),
        most_complex=max_fn,
    )


# ---------------------------------------------------------------------------
# Code example extraction from tests
# ---------------------------------------------------------------------------


@dataclass
class CodeExample:
    """A usage example extracted from test code."""
    source_file: str
    function_name: str
    code: str


_TEST_FUNC_RE = re.compile(
    r"^(def (test_\w+)\(.*?\):.*?)(?=\ndef |\Z)",
    re.MULTILINE | re.DOTALL,
)


def extract_code_examples(file_contents: dict[str, str]) -> list[CodeExample]:
    """Extract code usage examples from test files.

    Parses test functions and extracts the setup/action lines
    (strips assert statements) as usage examples.
    """
    examples = []

    for filepath, content in file_contents.items():
        # Only process test files
        basename = filepath.split("/")[-1]
        if not basename.startswith("test_"):
            continue

        for match in _TEST_FUNC_RE.finditer(content):
            full_body = match.group(1)
            func_name = match.group(2)

            # Extract code lines (strip asserts and decorators)
            code_lines = []
            for line in full_body.split("\n")[1:]:  # skip def line
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("assert "):
                    continue
                if stripped.startswith("@"):
                    continue
                code_lines.append(stripped)

            if code_lines:
                examples.append(CodeExample(
                    source_file=filepath,
                    function_name=func_name,
                    code="\n".join(code_lines),
                ))

    return examples
