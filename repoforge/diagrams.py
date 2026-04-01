"""
diagrams.py - Auto-generate Mermaid architecture diagrams from codebase analysis.

Generates three types of diagrams from CodeGraph and scanner data:
  1. Module dependency graph — flowchart showing import relationships
  2. Directory structure diagram — graph visualizing project hierarchy
  3. Call flow diagrams — sequence diagrams for entry point call chains

All output is Mermaid markdown (```mermaid blocks) suitable for embedding
in generated documentation.
"""

import logging
import re
from collections import defaultdict
from pathlib import Path

from .graph import CodeGraph

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mermaid helpers (shared)
# ---------------------------------------------------------------------------

def _mermaid_id(raw: str) -> str:
    """Convert a path/id to a valid Mermaid node identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw)


def _mermaid_safe(text: str) -> str:
    """Escape text for use in Mermaid labels."""
    return re.sub(r"[\"'\[\]{}|<>]", "", text)


# ---------------------------------------------------------------------------
# 1. Dependency diagram
# ---------------------------------------------------------------------------

def generate_dependency_diagram(graph: CodeGraph, max_nodes: int = 40) -> str:
    """Generate a Mermaid flowchart of module dependencies grouped by directory.

    Groups modules by their parent directory instead of the graph's layer field,
    producing a more intuitive visual grouping. Caps output at max_nodes for
    readability.

    Args:
        graph: A CodeGraph with module nodes and import/depends_on edges.
        max_nodes: Maximum modules to include (most-connected first).

    Returns:
        Mermaid flowchart string (without fences).
    """
    module_nodes = [n for n in graph.nodes if n.node_type == "module"]
    import_edges = [
        e for e in graph.edges
        if e.edge_type in ("imports", "depends_on")
    ]

    if not module_nodes:
        return "graph LR\n    empty[No modules detected]"

    # Rank by connection count, take top N
    connections: dict[str, int] = defaultdict(int)
    for e in import_edges:
        connections[e.source] += 1
        connections[e.target] += 1

    ranked = sorted(module_nodes, key=lambda n: connections.get(n.id, 0), reverse=True)
    selected = ranked[:max_nodes]
    selected_ids = {n.id for n in selected}

    # Group by parent directory
    by_dir: dict[str, list] = defaultdict(list)
    for n in selected:
        parent = str(Path(n.file_path).parent) if n.file_path else "root"
        parent = parent if parent != "." else "root"
        by_dir[parent].append(n)

    lines = ["graph LR"]

    # Render subgraphs per directory
    for dir_name, nodes in sorted(by_dir.items()):
        safe_dir = _mermaid_id(dir_name)
        display_name = _mermaid_safe(dir_name)
        lines.append(f"    subgraph {safe_dir}[{display_name}]")
        for n in nodes:
            safe_id = _mermaid_id(n.id)
            safe_label = _mermaid_safe(n.name)
            lines.append(f"        {safe_id}[{safe_label}]")
        lines.append("    end")

    # Render edges between selected nodes
    for e in import_edges:
        if e.source in selected_ids and e.target in selected_ids:
            src = _mermaid_id(e.source)
            tgt = _mermaid_id(e.target)
            lines.append(f"    {src} --> {tgt}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. Directory structure diagram
# ---------------------------------------------------------------------------

def generate_directory_diagram(files: list[str], max_depth: int = 3) -> str:
    """Generate a Mermaid graph showing project directory hierarchy.

    Builds a tree of directories from the file list, capped at max_depth.
    Each directory node shows the number of files it contains.

    Args:
        files: List of relative file paths.
        max_depth: Maximum directory depth to show (default 3).

    Returns:
        Mermaid graph string (without fences).
    """
    if not files:
        return "graph TD\n    empty[No files detected]"

    # Build directory tree with file counts
    dir_files: dict[str, int] = defaultdict(int)
    dir_children: dict[str, set] = defaultdict(set)

    for f in files:
        parts = Path(f).parts
        # Count file in its parent directory
        if len(parts) > 1:
            parent = str(Path(*parts[:-1]))
        else:
            parent = "."
        dir_files[parent] += 1

        # Build parent-child relationships between directories
        for depth in range(min(len(parts) - 1, max_depth)):
            if depth == 0:
                dir_path = parts[0]
                dir_children["."].add(dir_path)
            else:
                dir_path = str(Path(*parts[: depth + 1]))
                parent_path = str(Path(*parts[:depth]))
                dir_children[parent_path].add(dir_path)

    # Ensure root exists
    if "." not in dir_files and "." not in dir_children:
        # Files at root level
        root_files = sum(1 for f in files if "/" not in f and "\\" not in f)
        if root_files:
            dir_files["."] = root_files

    lines = ["graph TD"]

    # Render root
    root_count = dir_files.get(".", 0)
    lines.append(f'    root(["/ ({root_count} files)"])')

    # BFS through directory tree
    visited: set[str] = {"."}
    queue = ["."]

    while queue:
        current = queue.pop(0)
        current_id = _mermaid_id(current) if current != "." else "root"

        for child in sorted(dir_children.get(current, [])):
            if child in visited:
                continue
            visited.add(child)

            child_id = _mermaid_id(child)
            child_name = Path(child).name
            child_count = dir_files.get(child, 0)
            child_label = _mermaid_safe(f"{child_name}/ ({child_count} files)")
            lines.append(f'    {current_id} --> {child_id}["{child_label}"]')

            # Check depth before adding to queue
            depth = len(Path(child).parts)
            if depth < max_depth:
                queue.append(child)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. Call flow diagram
# ---------------------------------------------------------------------------

# Regex patterns for function calls (Python, TS/JS)
_PY_FUNC_DEF_RE = re.compile(r"^def\s+(\w+)\s*\(", re.MULTILINE)
_PY_FUNC_CALL_RE = re.compile(r"(?<!\bdef\s)(?<!\bclass\s)\b(\w+)\s*\(")

_JS_FUNC_DEF_RE = re.compile(
    r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(|"
    r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(?",
)
_JS_FUNC_CALL_RE = re.compile(r"\b(\w+)\s*\(")

# Python keywords/builtins to skip
_SKIP_NAMES = frozenset({
    "if", "for", "while", "with", "return", "yield", "raise", "assert",
    "print", "len", "range", "str", "int", "float", "bool", "list", "dict",
    "set", "tuple", "type", "isinstance", "issubclass", "super", "property",
    "staticmethod", "classmethod", "lambda", "import", "from", "class", "def",
    "True", "False", "None", "self", "cls", "async", "await",
    # JS/TS builtins
    "require", "console", "setTimeout", "setInterval", "Promise", "Array",
    "Object", "String", "Number", "Boolean", "Map", "Set", "Date", "Error",
    "JSON", "Math", "RegExp", "Symbol", "Function", "Proxy", "Reflect",
})


def _extract_functions_and_calls(
    content: str, language: str,
) -> tuple[list[str], dict[str, list[str]]]:
    """Extract function definitions and their call targets from source code.

    Returns:
        (function_names, calls_map) where calls_map maps function_name → [called_names]
    """
    if language == "python":
        func_def_re = _PY_FUNC_DEF_RE
        func_call_re = _PY_FUNC_CALL_RE
    else:
        func_def_re = _JS_FUNC_DEF_RE
        func_call_re = _JS_FUNC_CALL_RE

    # Find all function definitions with their line positions
    func_defs: list[tuple[str, int]] = []
    for m in func_def_re.finditer(content):
        name = m.group(1)
        if not name and m.lastindex and m.lastindex >= 2:
            name = m.group(2)
        if name and name not in _SKIP_NAMES:
            func_defs.append((name, m.start()))

    func_names = [f[0] for f in func_defs]

    if not func_defs:
        return [], {}

    # For each function, find calls within its body (until next function def)
    lines = content.split("\n")
    calls_map: dict[str, list[str]] = {}

    for i, (fname, start_pos) in enumerate(func_defs):
        # Find the end of this function's body (next function def or EOF)
        if i + 1 < len(func_defs):
            end_pos = func_defs[i + 1][1]
        else:
            end_pos = len(content)

        body = content[start_pos:end_pos]
        calls = []
        for m in func_call_re.finditer(body):
            called = m.group(1)
            if (
                called
                and called not in _SKIP_NAMES
                and called != fname  # skip recursion
                and called not in calls  # dedup
            ):
                calls.append(called)

        if calls:
            calls_map[fname] = calls

    return func_names, calls_map


def generate_call_flow_diagram(
    root_dir: str,
    entry_file: str,
    files: list[str],
    max_depth: int = 3,
) -> str:
    """Generate a Mermaid sequence diagram tracing calls from an entry point.

    Reads the entry file, finds defined functions and their calls, then
    traces call chains across files up to max_depth. Only follows calls
    to functions defined in the project (not external dependencies).

    Args:
        root_dir: Absolute path to the project root.
        entry_file: Relative path to the entry point file.
        files: List of all relative file paths in the project.
        max_depth: Maximum call chain depth (default 3).

    Returns:
        Mermaid sequence diagram string (without fences).
    """
    root = Path(root_dir)

    # Determine language from extension
    ext = Path(entry_file).suffix.lower()
    if ext == ".py":
        language = "python"
    elif ext in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
        language = "javascript"
    else:
        return f"sequenceDiagram\n    Note over Entry: Unsupported file type: {ext}"

    # Build a global function → file index
    func_to_file: dict[str, str] = {}
    file_calls: dict[str, dict[str, list[str]]] = {}

    # Only analyze files of the same language family
    target_exts = {".py"} if language == "python" else {".ts", ".tsx", ".js", ".jsx", ".mjs"}

    for fpath in files:
        if Path(fpath).suffix.lower() not in target_exts:
            continue
        abs_path = root / fpath
        try:
            content = abs_path.read_text(errors="replace")
        except OSError:
            continue

        func_names, calls_map = _extract_functions_and_calls(content, language)
        for fn in func_names:
            if fn not in func_to_file:  # first definition wins
                func_to_file[fn] = fpath
        if calls_map:
            file_calls[fpath] = calls_map

    # Trace from entry file
    entry_calls = file_calls.get(entry_file, {})
    if not entry_calls:
        return (
            "sequenceDiagram\n"
            f"    Note over {_mermaid_safe(Path(entry_file).stem)}: No traceable calls found"
        )

    lines = ["sequenceDiagram"]
    visited_calls: set[tuple[str, str]] = set()
    entry_name = _mermaid_safe(Path(entry_file).stem)

    def _trace(caller_file: str, caller_func: str, depth: int) -> None:
        if depth > max_depth:
            return

        caller_module = _mermaid_safe(Path(caller_file).stem)
        calls = file_calls.get(caller_file, {}).get(caller_func, [])

        for called_func in calls:
            target_file = func_to_file.get(called_func)
            if not target_file:
                continue

            call_key = (caller_func, called_func)
            if call_key in visited_calls:
                continue
            visited_calls.add(call_key)

            target_module = _mermaid_safe(Path(target_file).stem)
            lines.append(
                f"    {caller_module}->>+{target_module}: {_mermaid_safe(called_func)}()"
            )

            # Recurse into the called function
            _trace(target_file, called_func, depth + 1)

            lines.append(f"    {target_module}-->>-{caller_module}: return")

    # Start tracing from each function in the entry file
    for func_name in entry_calls:
        _trace(entry_file, func_name, 1)

    if len(lines) == 1:
        lines.append(
            f"    Note over {entry_name}: No internal calls traced"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. Orchestrator — generate all diagrams combined
# ---------------------------------------------------------------------------

def generate_all_diagrams(
    root_dir: str,
    graph: CodeGraph,
    files: list[str],
    *,
    max_dep_nodes: int = 40,
    max_dir_depth: int = 3,
    max_call_depth: int = 3,
) -> str:
    """Generate all diagram types and combine into a single markdown string.

    The output contains fenced ```mermaid blocks suitable for embedding
    in documentation chapters.

    Args:
        root_dir: Absolute path to the project root.
        graph: Pre-built CodeGraph.
        files: List of relative file paths.
        max_dep_nodes: Cap for dependency diagram nodes.
        max_dir_depth: Cap for directory diagram depth.
        max_call_depth: Cap for call flow diagram depth.

    Returns:
        Markdown string with all diagrams as fenced mermaid blocks.
    """
    sections: list[str] = []

    # 1. Dependency diagram
    dep = generate_dependency_diagram(graph, max_nodes=max_dep_nodes)
    sections.append(
        "### Module Dependencies\n\n"
        "```mermaid\n" + dep + "\n```"
    )

    # 2. Directory structure
    dir_diag = generate_directory_diagram(files, max_depth=max_dir_depth)
    sections.append(
        "### Directory Structure\n\n"
        "```mermaid\n" + dir_diag + "\n```"
    )

    # 3. Call flow for detected entry points
    entry_points = _detect_entry_points(root_dir, files)
    for entry in entry_points[:2]:  # Cap at 2 entry points
        call_diag = generate_call_flow_diagram(
            root_dir, entry, files, max_depth=max_call_depth,
        )
        entry_name = Path(entry).stem
        sections.append(
            f"### Call Flow: {entry_name}\n\n"
            "```mermaid\n" + call_diag + "\n```"
        )

    return "\n\n".join(sections)


def _detect_entry_points(root_dir: str, files: list[str]) -> list[str]:
    """Detect likely entry point files from a file list.

    Looks for common patterns: main.py, app.py, index.ts, server.ts, cli.py, etc.
    """
    entry_patterns = [
        re.compile(r"(?:^|/)main\.(?:py|ts|js)$"),
        re.compile(r"(?:^|/)app\.(?:py|ts|js)$"),
        re.compile(r"(?:^|/)index\.(?:ts|js|tsx|jsx)$"),
        re.compile(r"(?:^|/)server\.(?:py|ts|js)$"),
        re.compile(r"(?:^|/)cli\.py$"),
        re.compile(r"(?:^|/)__main__\.py$"),
    ]

    entries = []
    for f in files:
        for pattern in entry_patterns:
            if pattern.search(f):
                entries.append(f)
                break

    return entries
