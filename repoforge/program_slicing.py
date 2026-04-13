"""Program slicing — compute the minimal set of lines to understand a change.

Given a file and a target line number, computes the backward and forward
program slice: lines that AFFECT the target (backward) and lines AFFECTED
BY the target (forward).

Strategy:
  1. Parse the file with AST (Python) or regex (other languages)
  2. Identify which function/class the target line belongs to
  3. Trace variable definitions and usages within that scope
  4. Include import lines that feed into the slice
  5. Include dependent lines from the same file

The result is the minimal set of lines an LLM needs to understand the
change context at a given line.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class SliceLine:
    """A line included in the program slice."""

    line_number: int
    """1-indexed line number."""

    content: str
    """The actual line content."""

    reason: str
    """Why this line is in the slice: 'target', 'def', 'use', 'import', 'control', 'scope'."""


@dataclass
class ProgramSlice:
    """Result of a program slice computation."""

    file: str
    """Relative file path."""

    target_line: int
    """The target line number (1-indexed)."""

    target_content: str
    """Content of the target line."""

    scope_name: str
    """Name of the enclosing function/class, or '<module>' for top-level."""

    lines: list[SliceLine] = field(default_factory=list)
    """All lines in the slice, sorted by line number."""

    total_file_lines: int = 0
    """Total lines in the original file."""

    @property
    def reduction_ratio(self) -> float:
        """How much of the file was eliminated (0.0 = no reduction, 1.0 = all)."""
        if self.total_file_lines == 0:
            return 0.0
        return 1.0 - (len(self.lines) / self.total_file_lines)

    @property
    def line_numbers(self) -> list[int]:
        """Sorted list of line numbers in the slice."""
        return sorted(sl.line_number for sl in self.lines)


# ---------------------------------------------------------------------------
# Python AST-based slicer
# ---------------------------------------------------------------------------


class _PythonVisitor(ast.NodeVisitor):
    """Collect variable defs, uses, and control flow from Python AST."""

    def __init__(self) -> None:
        self.assignments: dict[str, list[int]] = {}  # name -> [line numbers]
        self.usages: dict[str, list[int]] = {}  # name -> [line numbers]
        self.function_ranges: list[tuple[str, int, int]] = []  # (name, start, end)
        self.class_ranges: list[tuple[str, int, int]] = []
        self.control_flow_lines: list[int] = []  # if/for/while/with/try
        self.import_lines: list[int] = []
        self.import_names: dict[str, int] = {}  # imported name -> line
        self.decorator_lines: list[int] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        end = getattr(node, "end_lineno", node.lineno)
        self.function_ranges.append((node.name, node.lineno, end))
        # Include decorators
        for dec in node.decorator_list:
            self.decorator_lines.append(dec.lineno)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        end = getattr(node, "end_lineno", node.lineno)
        self.class_ranges.append((node.name, node.lineno, end))
        for dec in node.decorator_list:
            self.decorator_lines.append(dec.lineno)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            for name in _extract_names(target):
                self.assignments.setdefault(name, []).append(node.lineno)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        for name in _extract_names(node.target):
            self.assignments.setdefault(name, []).append(node.lineno)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.target:
            for name in _extract_names(node.target):
                self.assignments.setdefault(name, []).append(node.lineno)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.usages.setdefault(node.id, []).append(node.lineno)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        self.import_lines.append(node.lineno)
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name.split(".")[-1]
            self.import_names[name] = node.lineno
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.import_lines.append(node.lineno)
        if node.names:
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                self.import_names[name] = node.lineno
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        self.control_flow_lines.append(node.lineno)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.control_flow_lines.append(node.lineno)
        # Loop variable is an assignment
        for name in _extract_names(node.target):
            self.assignments.setdefault(name, []).append(node.lineno)
        self.generic_visit(node)

    visit_AsyncFor = visit_For

    def visit_While(self, node: ast.While) -> None:
        self.control_flow_lines.append(node.lineno)
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self.control_flow_lines.append(node.lineno)
        for item in node.items:
            if item.optional_vars:
                for name in _extract_names(item.optional_vars):
                    self.assignments.setdefault(name, []).append(node.lineno)
        self.generic_visit(node)

    visit_AsyncWith = visit_With

    def visit_Try(self, node: ast.Try) -> None:
        self.control_flow_lines.append(node.lineno)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        # Return statements use variables
        self.generic_visit(node)


def _extract_names(node: ast.AST) -> list[str]:
    """Extract variable names from an assignment target."""
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for elt in node.elts:
            names.extend(_extract_names(elt))
        return names
    if isinstance(node, ast.Starred):
        return _extract_names(node.value)
    if isinstance(node, ast.Attribute):
        # e.g., self.x — track the root name
        return _extract_names(node.value)
    return []


def _slice_python(content: str, target_line: int) -> tuple[set[int], str, dict[str, str]]:
    """Compute program slice for Python using AST.

    Returns:
        (line_numbers, scope_name, reasons_map)
        where reasons_map maps line_number -> reason string
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Fall back to regex slicer
        return _slice_generic(content, target_line)

    visitor = _PythonVisitor()
    visitor.visit(tree)

    lines = content.split("\n")
    slice_lines: set[int] = set()
    reasons: dict[str, str] = {}  # str(line_num) -> reason

    # 1. Always include the target line
    slice_lines.add(target_line)
    reasons[str(target_line)] = "target"

    # 2. Find enclosing scope
    scope_name = "<module>"
    scope_start = 1
    scope_end = len(lines)

    # Check functions first (more specific than classes)
    for name, start, end in visitor.function_ranges:
        if start <= target_line <= end:
            if end - start < scope_end - scope_start:
                scope_name = name
                scope_start = start
                scope_end = end

    # Check classes if no function found
    if scope_name == "<module>":
        for name, start, end in visitor.class_ranges:
            if start <= target_line <= end:
                scope_name = name
                scope_start = start
                scope_end = end

    # Include scope definition line
    slice_lines.add(scope_start)
    reasons[str(scope_start)] = "scope"

    # 3. Find variables used on the target line
    target_vars_used: set[str] = set()
    target_vars_defined: set[str] = set()

    for name, line_nums in visitor.usages.items():
        if target_line in line_nums:
            target_vars_used.add(name)

    for name, line_nums in visitor.assignments.items():
        if target_line in line_nums:
            target_vars_defined.add(name)

    # 4. Backward slice: find definitions of variables used on target line
    all_relevant_vars = set(target_vars_used)
    # Iterate to find transitive dependencies (limited to 3 rounds)
    for _ in range(3):
        new_vars: set[str] = set()
        for var in list(all_relevant_vars):
            if var in visitor.assignments:
                for def_line in visitor.assignments[var]:
                    if scope_start <= def_line <= scope_end and def_line != target_line:
                        slice_lines.add(def_line)
                        reasons.setdefault(str(def_line), "def")
                        # Find vars used on this definition line
                        for other_var, use_lines in visitor.usages.items():
                            if def_line in use_lines:
                                new_vars.add(other_var)
        if not new_vars - all_relevant_vars:
            break
        all_relevant_vars |= new_vars

    # 5. Forward slice: find usages of variables defined on target line
    for var in target_vars_defined:
        if var in visitor.usages:
            for use_line in visitor.usages[var]:
                if scope_start <= use_line <= scope_end:
                    slice_lines.add(use_line)
                    reasons.setdefault(str(use_line), "use")

    # 6. Include relevant imports
    for var in all_relevant_vars | target_vars_defined:
        if var in visitor.import_names:
            imp_line = visitor.import_names[var]
            slice_lines.add(imp_line)
            reasons.setdefault(str(imp_line), "import")

    # 7. Include control flow lines within scope that affect the target
    for cf_line in visitor.control_flow_lines:
        if scope_start <= cf_line < target_line:
            # Check if target is inside this control block
            # Simple heuristic: if target indentation > control line indentation
            if cf_line <= len(lines) and target_line <= len(lines):
                cf_indent = len(lines[cf_line - 1]) - len(lines[cf_line - 1].lstrip())
                tgt_indent = len(lines[target_line - 1]) - len(lines[target_line - 1].lstrip())
                if tgt_indent > cf_indent:
                    slice_lines.add(cf_line)
                    reasons.setdefault(str(cf_line), "control")

    # 8. Include decorator lines for the scope
    for dec_line in visitor.decorator_lines:
        if dec_line == scope_start - 1 or (scope_start - 3 <= dec_line < scope_start):
            slice_lines.add(dec_line)
            reasons.setdefault(str(dec_line), "scope")

    return slice_lines, scope_name, reasons


# ---------------------------------------------------------------------------
# Generic regex-based slicer (non-Python files)
# ---------------------------------------------------------------------------

# Patterns for function/method definitions
_FUNC_PATTERNS = [
    re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)"),  # JS/TS
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\("),  # arrow
    re.compile(r"^\s*func\s+(\w+)"),  # Go
    re.compile(r"^\s*(?:pub\s+)?fn\s+(\w+)"),  # Rust
    re.compile(r"^\s*(?:public|private|protected|static|\s)*\s+\w+\s+(\w+)\s*\("),  # Java
    re.compile(r"^\s*def\s+(\w+)"),  # Python fallback
]

# Variable assignment patterns
_ASSIGN_PATTERN = re.compile(
    r"^\s*(?:const|let|var|val|mut)?\s*(\w+)\s*(?::[\w\[\]<>, |]+)?\s*="
)

# Import patterns
_IMPORT_PATTERN = re.compile(
    r"^\s*(?:import|from|require|use|include)\b"
)


def _slice_generic(content: str, target_line: int) -> tuple[set[int], str, dict[str, str]]:
    """Regex-based program slice for non-Python languages."""
    lines = content.split("\n")
    slice_lines: set[int] = set()
    reasons: dict[str, str] = {}

    if target_line > len(lines) or target_line < 1:
        return slice_lines, "<module>", reasons

    # Always include target
    slice_lines.add(target_line)
    reasons[str(target_line)] = "target"

    # Find enclosing function
    scope_name = "<module>"
    scope_start = 1
    scope_end = len(lines)

    target_indent = len(lines[target_line - 1]) - len(lines[target_line - 1].lstrip())

    for i in range(target_line - 1, -1, -1):
        line = lines[i]
        for pat in _FUNC_PATTERNS:
            m = pat.match(line)
            if m:
                func_indent = len(line) - len(line.lstrip())
                if func_indent < target_indent or i + 1 == target_line:
                    scope_name = m.group(1)
                    scope_start = i + 1
                    # Find scope end (next line at same or lesser indent)
                    for j in range(target_line, len(lines)):
                        if lines[j].strip() and (len(lines[j]) - len(lines[j].lstrip())) <= func_indent:
                            scope_end = j
                            break
                    else:
                        scope_end = len(lines)
                    slice_lines.add(scope_start)
                    reasons[str(scope_start)] = "scope"
                    break
        if scope_name != "<module>":
            break

    # Extract variable names used on target line
    target_text = lines[target_line - 1]
    target_words = set(re.findall(r"\b([a-zA-Z_]\w*)\b", target_text))

    # Find definitions of those variables within scope
    for i in range(scope_start - 1, scope_end):
        if i + 1 == target_line:
            continue
        line = lines[i]
        m = _ASSIGN_PATTERN.match(line)
        if m and m.group(1) in target_words:
            slice_lines.add(i + 1)
            reasons.setdefault(str(i + 1), "def")

    # Find usages of variables defined on target line
    target_assign = _ASSIGN_PATTERN.match(target_text)
    if target_assign:
        defined_var = target_assign.group(1)
        for i in range(scope_start - 1, scope_end):
            if i + 1 == target_line:
                continue
            if re.search(r"\b" + re.escape(defined_var) + r"\b", lines[i]):
                slice_lines.add(i + 1)
                reasons.setdefault(str(i + 1), "use")

    # Include import lines that reference target variables
    for i, line in enumerate(lines):
        if _IMPORT_PATTERN.match(line):
            for word in target_words:
                if word in line:
                    slice_lines.add(i + 1)
                    reasons.setdefault(str(i + 1), "import")
                    break

    return slice_lines, scope_name, reasons


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_slice(
    repo_path: str,
    file_path: str,
    target_line: int,
) -> ProgramSlice:
    """Compute a program slice for a given file and line.

    Args:
        repo_path: Path to the repository root.
        file_path: Relative path to the file within the repo.
        target_line: 1-indexed line number to slice around.

    Returns:
        ProgramSlice with the minimal set of lines needed to understand
        the change at the target line.
    """
    root = Path(repo_path).resolve()
    abs_path = root / file_path

    try:
        content = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.warning("Cannot read %s", abs_path)
        return ProgramSlice(
            file=file_path,
            target_line=target_line,
            target_content="",
            scope_name="<error>",
        )

    lines = content.split("\n")
    total_lines = len(lines)

    if target_line < 1 or target_line > total_lines:
        return ProgramSlice(
            file=file_path,
            target_line=target_line,
            target_content="",
            scope_name="<out-of-range>",
            total_file_lines=total_lines,
        )

    target_content = lines[target_line - 1]

    # Choose slicer based on file extension
    if file_path.endswith(".py"):
        slice_line_nums, scope_name, reasons = _slice_python(content, target_line)
    else:
        slice_line_nums, scope_name, reasons = _slice_generic(content, target_line)

    # Build SliceLine objects
    slice_objs: list[SliceLine] = []
    for ln in sorted(slice_line_nums):
        if 1 <= ln <= total_lines:
            slice_objs.append(SliceLine(
                line_number=ln,
                content=lines[ln - 1],
                reason=reasons.get(str(ln), "related"),
            ))

    return ProgramSlice(
        file=file_path,
        target_line=target_line,
        target_content=target_content,
        scope_name=scope_name,
        lines=slice_objs,
        total_file_lines=total_lines,
    )


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


def format_slice(ps: ProgramSlice) -> str:
    """Format a program slice as human-readable text."""
    lines: list[str] = []
    lines.append(f"## Program Slice: `{ps.file}` line {ps.target_line}")
    lines.append(f"**Scope**: `{ps.scope_name}`")
    lines.append(f"**Slice lines**: {len(ps.lines)} / {ps.total_file_lines} "
                 f"({ps.reduction_ratio:.0%} reduction)")
    lines.append("")

    if not ps.lines:
        lines.append("No slice computed (file may be empty or line out of range).")
        return "\n".join(lines)

    lines.append("```")
    prev_ln = 0
    for sl in ps.lines:
        # Show gaps
        if prev_ln and sl.line_number > prev_ln + 1:
            lines.append("    ...")
        marker = " >>>" if sl.reason == "target" else f" [{sl.reason}]"
        lines.append(f"{sl.line_number:4d}{marker}  {sl.content}")
        prev_ln = sl.line_number
    lines.append("```")
    lines.append("")

    # Legend
    lines.append("**Legend**: `>>>` = target line, "
                 "`[def]` = variable definition, "
                 "`[use]` = variable usage, "
                 "`[import]` = import, "
                 "`[control]` = control flow, "
                 "`[scope]` = enclosing scope")

    return "\n".join(lines)
