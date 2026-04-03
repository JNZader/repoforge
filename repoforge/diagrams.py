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

    # 4. Symbol-level dependencies
    sym_diag = generate_symbol_diagram(root_dir, files)
    if sym_diag:
        sections.append(
            "### Symbol Dependencies\n\n"
            "```mermaid\n" + sym_diag + "\n```"
        )

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# 5. Symbol-level dependency diagram
# ---------------------------------------------------------------------------


def generate_symbol_diagram(
    root_dir: str,
    files: list[str],
    max_symbols: int = 60,
) -> str:
    """Generate a Mermaid flowchart of symbol-level (function/class) dependencies.

    Uses regex-based symbol extraction and call graph analysis to show
    which functions call which across the codebase.

    Args:
        root_dir: Absolute path to the project root.
        files: List of relative file paths.
        max_symbols: Maximum symbols to include (default 60).

    Returns:
        Mermaid flowchart string (without fences), or empty string if
        no symbols or edges were found.
    """
    try:
        from .symbols import build_symbol_graph, render_symbol_mermaid

        graph = build_symbol_graph(root_dir, files)
        if not graph.symbols or not graph.edges:
            return ""

        return render_symbol_mermaid(graph, max_symbols=max_symbols)
    except (ImportError, OSError, ValueError, RuntimeError) as e:
        # ImportError: symbols module; OSError: file read; ValueError/RuntimeError: graph errors
        logger.debug("Symbol diagram generation failed: %s", e)
        return ""


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


# ---------------------------------------------------------------------------
# 6. SQL → ERD diagram
# ---------------------------------------------------------------------------

# Regex patterns for SQL CREATE TABLE parsing
_SQL_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?\s*\(",
    re.IGNORECASE,
)
_SQL_COLUMN_RE = re.compile(
    r"^\s+[`\"']?(\w+)[`\"']?\s+([\w()]+)",
    re.MULTILINE,
)
_SQL_FK_RE = re.compile(
    r"REFERENCES\s+[`\"']?(\w+)[`\"']?\s*\(\s*[`\"']?(\w+)[`\"']?\s*\)",
    re.IGNORECASE,
)
_SQL_PK_RE = re.compile(
    r"PRIMARY\s+KEY",
    re.IGNORECASE,
)

# SQL keywords that are NOT column names
_SQL_KEYWORDS = frozenset({
    "primary", "key", "foreign", "unique", "check", "constraint",
    "index", "references", "not", "null", "default", "auto_increment",
    "autoincrement", "serial", "create", "table", "if", "exists",
    "engine", "charset", "collate", "comment",
})


def generate_erd_diagram(sql: str) -> str:
    """Generate a Mermaid erDiagram from SQL CREATE TABLE statements.

    Parses CREATE TABLE definitions to extract table names, column names
    with types, and foreign key relationships.

    Args:
        sql: Raw SQL string containing CREATE TABLE statements.

    Returns:
        Mermaid erDiagram string (without fences).
    """
    if not sql or not sql.strip():
        return "erDiagram\n    %% No tables detected"

    tables: dict[str, list[tuple[str, str, bool]]] = {}  # name -> [(col, type, is_pk)]
    relationships: list[tuple[str, str, str, str]] = []  # (from_table, to_table, from_col, to_col)

    # Split into individual CREATE TABLE blocks
    table_matches = list(_SQL_CREATE_TABLE_RE.finditer(sql))
    if not table_matches:
        return "erDiagram\n    %% No tables detected"

    for i, match in enumerate(table_matches):
        table_name = match.group(1)
        start = match.end()
        # Find the end of this CREATE TABLE (next CREATE TABLE or end of string)
        end = table_matches[i + 1].start() if i + 1 < len(table_matches) else len(sql)
        block = sql[start:end]

        # Find the closing paren of CREATE TABLE
        paren_depth = 1
        block_end = 0
        for ci, ch in enumerate(block):
            if ch == "(":
                paren_depth += 1
            elif ch == ")":
                paren_depth -= 1
                if paren_depth == 0:
                    block_end = ci
                    break
        if block_end:
            block = block[:block_end]

        columns: list[tuple[str, str, bool]] = []

        for line in block.split("\n"):
            line_stripped = line.strip().rstrip(",")
            if not line_stripped:
                continue

            # Skip pure constraint lines
            first_word = line_stripped.split()[0].lower().strip("`\"'") if line_stripped.split() else ""
            if first_word in _SQL_KEYWORDS:
                continue

            # Extract column
            col_match = _SQL_COLUMN_RE.match(line)
            if col_match:
                col_name = col_match.group(1).lower()
                col_type = col_match.group(2)
                if col_name not in _SQL_KEYWORDS:
                    is_pk = bool(_SQL_PK_RE.search(line))
                    columns.append((col_name, col_type, is_pk))

            # Extract FK references
            fk_match = _SQL_FK_RE.search(line)
            if fk_match:
                ref_table = fk_match.group(1)
                ref_col = fk_match.group(2)
                # Find the column name this FK belongs to
                fk_col_match = _SQL_COLUMN_RE.match(line)
                fk_col = fk_col_match.group(1) if fk_col_match else "unknown"
                relationships.append((table_name, ref_table, fk_col, ref_col))

        if columns:
            tables[table_name] = columns

    if not tables:
        return "erDiagram\n    %% No tables detected"

    lines = ["erDiagram"]

    # Render relationships
    for from_table, to_table, from_col, to_col in relationships:
        if from_table in tables and to_table in tables:
            lines.append(
                f"    {to_table} ||--o{{ {from_table} : \"{from_col} -> {to_col}\""
            )

    # Render entities
    for table_name, columns in sorted(tables.items()):
        lines.append(f"    {table_name} {{")
        for col_name, col_type, is_pk in columns:
            safe_type = re.sub(r"[^a-zA-Z0-9_]", "", col_type)
            pk_marker = " PK" if is_pk else ""
            lines.append(f"        {safe_type} {col_name}{pk_marker}")
        lines.append("    }")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7. Kubernetes YAML → diagram
# ---------------------------------------------------------------------------

# Regex patterns for K8s YAML parsing (avoids PyYAML dependency)
_K8S_KIND_RE = re.compile(r"^kind:\s*(\S+)", re.MULTILINE)
_K8S_NAME_RE = re.compile(
    r"^metadata:\s*\n(?:\s+\S.*\n)*?\s+name:\s*(\S+)",
    re.MULTILINE,
)
_K8S_NAMESPACE_RE = re.compile(
    r"^metadata:\s*\n(?:\s+\S.*\n)*?\s+namespace:\s*(\S+)",
    re.MULTILINE,
)
_K8S_SELECTOR_RE = re.compile(
    r"selector:\s*\n(?:\s+matchLabels:\s*\n)?\s+app:\s*(\S+)",
    re.MULTILINE,
)
_K8S_LABELS_APP_RE = re.compile(
    r"labels:\s*\n\s+app:\s*(\S+)",
    re.MULTILINE,
)
_K8S_CONTAINER_IMAGE_RE = re.compile(
    r"image:\s*(\S+)",
    re.MULTILINE,
)
_K8S_SERVICE_TYPE_RE = re.compile(
    r"type:\s*(ClusterIP|NodePort|LoadBalancer|ExternalName)",
    re.MULTILINE,
)
_K8S_INGRESS_SVC_RE = re.compile(
    r"service:\s*\n\s+name:\s*(\S+)",
    re.MULTILINE,
)

# Resource types that represent workloads
_K8S_WORKLOADS = frozenset({
    "Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob", "ReplicaSet", "Pod",
})

# Resource shapes in Mermaid
_K8S_SHAPES: dict[str, tuple[str, str]] = {
    "Service": ("((", "))"),
    "Ingress": ("[[", "]]"),
    "ConfigMap": ("[/", "/]"),
    "Secret": ("[/", "/]"),
    "PersistentVolumeClaim": ("[(", ")]"),
    "Namespace": ("{{", "}}"),
}


def generate_k8s_diagram(yaml_content: str) -> str:
    """Generate a Mermaid flowchart from Kubernetes YAML manifests.

    Parses kind, metadata.name, selectors, and labels to build a graph
    of K8s resources and their relationships.

    Args:
        yaml_content: Raw YAML string (may contain multiple documents
            separated by ``---``).

    Returns:
        Mermaid flowchart string (without fences).
    """
    if not yaml_content or not yaml_content.strip():
        return "graph TD\n    empty[No Kubernetes resources detected]"

    # Split multi-document YAML
    documents = re.split(r"^---\s*$", yaml_content, flags=re.MULTILINE)

    resources: list[dict[str, str]] = []

    for doc in documents:
        doc = doc.strip()
        if not doc:
            continue

        kind_match = _K8S_KIND_RE.search(doc)
        name_match = _K8S_NAME_RE.search(doc)

        if not kind_match or not name_match:
            continue

        resource: dict[str, str] = {
            "kind": kind_match.group(1),
            "name": name_match.group(1),
            "raw": doc,
        }

        ns_match = _K8S_NAMESPACE_RE.search(doc)
        if ns_match:
            resource["namespace"] = ns_match.group(1)

        selector_match = _K8S_SELECTOR_RE.search(doc)
        if selector_match:
            resource["selector_app"] = selector_match.group(1)

        label_match = _K8S_LABELS_APP_RE.search(doc)
        if label_match:
            resource["label_app"] = label_match.group(1)

        svc_type_match = _K8S_SERVICE_TYPE_RE.search(doc)
        if svc_type_match:
            resource["service_type"] = svc_type_match.group(1)

        resources.append(resource)

    if not resources:
        return "graph TD\n    empty[No Kubernetes resources detected]"

    lines = ["graph TD"]

    # Build node ID map and render nodes
    node_ids: dict[str, str] = {}
    for r in resources:
        kind = r["kind"]
        name = r["name"]
        node_id = _mermaid_id(f"{kind}_{name}")
        node_ids[f"{kind}/{name}"] = node_id

        label = _mermaid_safe(f"{kind}: {name}")
        shape = _K8S_SHAPES.get(kind, ("[", "]"))
        if kind in _K8S_WORKLOADS:
            shape = ("[", "]")

        lines.append(f"    {node_id}{shape[0]}{label}{shape[1]}")

    # Build edges based on selector/label matching
    for r in resources:
        kind = r["kind"]
        name = r["name"]
        src_id = node_ids[f"{kind}/{name}"]

        # Service → Workload (selector → label match)
        if kind == "Service" and "selector_app" in r:
            app = r["selector_app"]
            for target in resources:
                if target["kind"] in _K8S_WORKLOADS and target.get("label_app") == app:
                    tgt_id = node_ids[f"{target['kind']}/{target['name']}"]
                    lines.append(f"    {src_id} -->|selects| {tgt_id}")

        # Ingress → Service
        if kind == "Ingress":
            for svc_match in _K8S_INGRESS_SVC_RE.finditer(r["raw"]):
                svc_name = svc_match.group(1)
                tgt_key = f"Service/{svc_name}"
                if tgt_key in node_ids:
                    tgt_id = node_ids[tgt_key]
                    lines.append(f"    {src_id} -->|routes| {tgt_id}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 8. OpenAPI spec → diagram
# ---------------------------------------------------------------------------


def generate_openapi_diagram(spec_content: str) -> str:
    """Generate a Mermaid class diagram from an OpenAPI 3.x specification.

    Parses paths (endpoints) and component schemas to show API structure
    and schema relationships. Supports JSON input; for YAML-format specs,
    falls back to regex extraction.

    Args:
        spec_content: Raw OpenAPI spec string (JSON or YAML).

    Returns:
        Mermaid classDiagram string (without fences).
    """
    import json as _json

    if not spec_content or not spec_content.strip():
        return "classDiagram\n    class NoSpec\n    NoSpec : No OpenAPI spec detected"

    spec: dict | None = None

    # Try JSON first
    try:
        spec = _json.loads(spec_content)
    except (ValueError, TypeError):
        pass

    # Fallback: regex-based YAML extraction
    if spec is None:
        return _parse_openapi_yaml_fallback(spec_content)

    # Validate it looks like OpenAPI
    if not isinstance(spec, dict) or ("openapi" not in spec and "swagger" not in spec):
        return "classDiagram\n    class NoSpec\n    NoSpec : No OpenAPI spec detected"

    lines = ["classDiagram"]
    schema_names: set[str] = set()
    endpoint_ids: dict[str, str] = {}
    schema_refs: list[tuple[str, str]] = []

    # Extract schemas from components.schemas (v3) or definitions (v2)
    schemas = spec.get("components", {}).get("schemas", {})
    if not schemas:
        schemas = spec.get("definitions", {})

    for schema_name, schema_def in schemas.items():
        if not isinstance(schema_def, dict):
            continue
        schema_names.add(schema_name)
        safe_name = _mermaid_id(schema_name)
        lines.append(f"    class {safe_name} {{")

        properties = schema_def.get("properties", {})
        for prop_name, prop_def in properties.items():
            if not isinstance(prop_def, dict):
                continue
            prop_type = prop_def.get("type", "object")

            # Track $ref relationships
            ref = prop_def.get("$ref", "")
            if ref:
                ref_name = ref.split("/")[-1]
                schema_refs.append((schema_name, ref_name))
                prop_type = ref_name

            items = prop_def.get("items", {})
            if isinstance(items, dict):
                item_ref = items.get("$ref", "")
                if item_ref:
                    ref_name = item_ref.split("/")[-1]
                    schema_refs.append((schema_name, ref_name))
                    prop_type = f"{ref_name}[]"

            lines.append(f"        +{prop_type} {_mermaid_safe(prop_name)}")
        lines.append("    }")

    # Extract paths/endpoints
    paths = spec.get("paths", {})
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            if method not in methods:
                continue
            op = methods[method]
            if not isinstance(op, dict):
                continue

            op_id = op.get("operationId", f"{method}_{path}")
            safe_id = _mermaid_id(op_id)
            endpoint_ids[safe_id] = f"{method.upper()} {path}"

            lines.append(f"    class {safe_id} {{")
            lines.append(f"        <<endpoint>>")
            lines.append(f"        +{method.upper()} {_mermaid_safe(path)}")
            lines.append("    }")

            # Find schema references in responses and requestBody
            _collect_openapi_refs(op, safe_id, schema_names, schema_refs, lines)

    # Render schema-to-schema relationships
    rendered_rels: set[tuple[str, str]] = set()
    for from_name, to_name in schema_refs:
        safe_from = _mermaid_id(from_name)
        safe_to = _mermaid_id(to_name)
        rel_key = (safe_from, safe_to)
        if rel_key not in rendered_rels and safe_from != safe_to:
            rendered_rels.add(rel_key)
            lines.append(f"    {safe_from} --> {safe_to}")

    if len(lines) == 1:
        lines.append("    class NoSpec\n    NoSpec : No OpenAPI spec detected")

    return "\n".join(lines)


def _collect_openapi_refs(
    operation: dict,
    endpoint_id: str,
    schema_names: set[str],
    schema_refs: list[tuple[str, str]],
    lines: list[str],
) -> None:
    """Walk an OpenAPI operation to find $ref links to schemas."""
    def _walk(obj: object) -> None:
        if isinstance(obj, dict):
            ref = obj.get("$ref", "")
            if isinstance(ref, str) and ref:
                ref_name = ref.split("/")[-1]
                if ref_name in schema_names:
                    schema_refs.append((endpoint_id, ref_name))
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    # Walk responses
    _walk(operation.get("responses", {}))
    # Walk requestBody
    _walk(operation.get("requestBody", {}))
    # Walk parameters
    _walk(operation.get("parameters", []))


def _parse_openapi_yaml_fallback(content: str) -> str:
    """Best-effort regex extraction for YAML-format OpenAPI specs."""
    lines = ["classDiagram"]

    # Extract paths
    path_re = re.compile(r"^\s{2}(/\S*):", re.MULTILINE)
    method_re = re.compile(r"^\s{4}(get|post|put|patch|delete):", re.MULTILINE)

    paths_found = []
    for m in path_re.finditer(content):
        path = m.group(1)
        # Find methods after this path
        region_start = m.end()
        next_path = path_re.search(content, region_start)
        region_end = next_path.start() if next_path else len(content)
        region = content[region_start:region_end]

        for method_match in method_re.finditer(region):
            method = method_match.group(1).upper()
            op_id = _mermaid_id(f"{method}_{path}")
            paths_found.append(op_id)
            lines.append(f"    class {op_id} {{")
            lines.append(f"        <<endpoint>>")
            lines.append(f"        +{method} {_mermaid_safe(path)}")
            lines.append("    }")

    # Extract schemas
    schema_re = re.compile(r"^\s{4}(\w+):\s*$", re.MULTILINE)
    in_schemas = False
    schemas_section = ""

    # Find the schemas section
    schemas_start = re.search(r"^\s{2}schemas:\s*$", content, re.MULTILINE)
    if schemas_start:
        schemas_section = content[schemas_start.end():]
        # Cut at next top-level key
        next_top = re.search(r"^\S", schemas_section, re.MULTILINE)
        if next_top:
            schemas_section = schemas_section[:next_top.start()]

        for sm in schema_re.finditer(schemas_section):
            schema_name = sm.group(1)
            safe_name = _mermaid_id(schema_name)
            lines.append(f"    class {safe_name} {{")
            lines.append(f"        <<schema>>")
            lines.append("    }")

    if len(lines) == 1:
        lines.append("    class NoSpec\n    NoSpec : No OpenAPI spec detected")

    return "\n".join(lines)
