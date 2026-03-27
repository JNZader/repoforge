"""
exporter.py - Flatten a repository into a single LLM-optimized markdown/XML file.

Inspired by Karpathy's rendergit (2.1K stars) and SWAGENT's token-optimized output.

No LLM calls needed — purely deterministic. Uses scanner.scan_repo() and
ripgrep.list_files() to gather all repo data, then serializes it as a single
document suitable for pasting into any LLM (Claude, ChatGPT, Gemini, etc.).

Output sections:
  1. Project Overview   — tech stack, entry points, project type
  2. Directory Tree     — full tree structure
  3. Key Definitions    — exported functions, classes, constants per file
  4. File Contents      — each file with path header and full content
"""

from pathlib import Path
from typing import Optional

from .scanner import scan_repo
from .ripgrep import extract_definitions, SUPPORTED_EXTENSIONS


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Characters per token (conservative estimate — avoids litellm dependency)
_CHARS_PER_TOKEN = 4

# Files to always skip when including contents
SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Pipfile.lock",
    "poetry.lock", "Cargo.lock", "composer.lock", "Gemfile.lock",
    "go.sum", ".DS_Store", "Thumbs.db",
}

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".avif",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".exe", ".dll", ".so", ".dylib", ".o", ".a",
    ".pyc", ".pyo", ".class", ".jar",
    ".db", ".sqlite", ".sqlite3",
    ".min.js", ".min.css",
}

SKIP_DIRS = {
    "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", ".nuxt", "coverage", ".pytest_cache", ".mypy_cache",
    ".git", "vendor", ".ruff_cache", ".tox", "htmlcov",
    ".eggs", "*.egg-info",
}

# Content file extensions (broader than source-only — includes configs, docs)
CONTENT_EXTENSIONS = SUPPORTED_EXTENSIONS | {
    ".md", ".txt", ".rst", ".toml", ".yaml", ".yml", ".json",
    ".cfg", ".ini", ".env", ".sh", ".bash", ".zsh", ".fish",
    ".dockerfile", ".sql", ".graphql", ".proto", ".html", ".css",
    ".scss", ".less", ".xml", ".csv",
}

MAX_FILE_SIZE = 100 * 1024  # 100KB per file


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def export_llm_view(
    workspace: str,
    output_path: Optional[str] = None,
    max_tokens: Optional[int] = None,
    include_contents: bool = True,
    fmt: str = "markdown",
    compress: bool = False,
) -> str:
    """
    Flatten a repository into a single LLM-optimized document.

    Args:
        workspace:        Path to the repo root.
        output_path:      If set, write the result to this file.
        max_tokens:       Optional token budget (uses char estimation).
        include_contents: If False, skip file contents (only tree + definitions).
        fmt:              Output format — "markdown" or "xml".
        compress:         If True, compress file contents to API surface only
                          using tree-sitter (falls back to first N lines).

    Returns:
        The generated document as a string.
    """
    root = Path(workspace).resolve()
    project_name = root.name

    # 1. Scan repo for structured data
    repo_map = scan_repo(str(root))

    # 2. Discover ALL files (not just source — also configs, docs)
    all_files = _discover_all_files(root)

    # 3. Extract definitions from source files
    source_files = [f for f in all_files if f.suffix.lower() in SUPPORTED_EXTENSIONS]
    definitions = extract_definitions(source_files, root)

    # 4. Build the document
    if fmt == "xml":
        doc = _build_xml(root, project_name, repo_map, all_files, definitions,
                         include_contents, max_tokens, compress)
    else:
        doc = _build_markdown(root, project_name, repo_map, all_files, definitions,
                              include_contents, max_tokens, compress)

    # 5. Optionally write to file
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(doc, encoding="utf-8")

    return doc


# ---------------------------------------------------------------------------
# File discovery (broader than ripgrep.list_files — includes non-source)
# ---------------------------------------------------------------------------

def _discover_all_files(root: Path) -> list[Path]:
    """
    Find all text files in the repo, respecting ignore patterns.
    Broader than ripgrep.list_files() — includes .md, .yaml, .toml, etc.
    """
    result = []
    try:
        for entry in sorted(root.rglob("*")):
            if not entry.is_file():
                continue
            try:
                rel_parts = entry.relative_to(root).parts
            except ValueError:
                continue
            # Skip ignored directories
            if any(part in SKIP_DIRS for part in rel_parts):
                continue
            # Skip by filename
            if entry.name in SKIP_FILENAMES:
                continue
            # Skip binary/asset extensions
            if entry.suffix.lower() in SKIP_EXTENSIONS:
                continue
            # Skip files that are too large
            try:
                if entry.stat().st_size > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue
            # Only include known text extensions (or extensionless small files)
            if entry.suffix.lower() in CONTENT_EXTENSIONS or entry.suffix == "":
                result.append(entry.resolve())
    except PermissionError:
        pass
    return result


# ---------------------------------------------------------------------------
# Directory tree builder
# ---------------------------------------------------------------------------

def _build_tree(root: Path, files: list[Path]) -> str:
    """Build a tree-style directory listing from a list of files."""
    tree: dict = {}
    for f in files:
        try:
            rel = f.relative_to(root)
        except ValueError:
            continue
        parts = rel.parts
        node = tree
        for part in parts:
            node = node.setdefault(part, {})

    lines = [f"{root.name}/"]
    _render_tree(tree, lines, prefix="")
    return "\n".join(lines)


def _render_tree(node: dict, lines: list[str], prefix: str):
    """Recursively render a tree dict into lines with box-drawing chars."""
    entries = sorted(node.keys(), key=lambda k: (not bool(node[k]), k))
    for i, name in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "--- " if is_last else "|-- "
        lines.append(f"{prefix}{connector}{name}")
        if node[name]:  # has children = directory
            extension = "    " if is_last else "|   "
            _render_tree(node[name], lines, prefix + extension)


# ---------------------------------------------------------------------------
# Token budget helpers
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> int:
    """Estimate token count from character count."""
    return len(text) // _CHARS_PER_TOKEN


def _prioritize_files(files: list[Path], root: Path, repo_map: dict) -> list[Path]:
    """
    Sort files by importance for token-budgeted output.
    Priority: entry points > config files > source files > tests > everything else.
    """
    entry_points = set(repo_map.get("entry_points", []))
    config_files = set(repo_map.get("config_files", []))

    def _priority(f: Path) -> tuple[int, str]:
        try:
            rel = str(f.relative_to(root))
        except ValueError:
            rel = f.name
        name = f.name.lower()
        # Priority 0: entry points (most important)
        if rel in entry_points:
            return (0, rel)
        # Priority 1: config files
        if rel in config_files or name in config_files:
            return (1, rel)
        # Priority 2: source code
        if f.suffix.lower() in SUPPORTED_EXTENSIONS:
            # Demote test files
            if "test" in name or rel.startswith("tests/") or rel.startswith("test/"):
                return (4, rel)
            return (2, rel)
        # Priority 3: docs and configs
        if f.suffix.lower() in {".md", ".toml", ".yaml", ".yml", ".json"}:
            return (3, rel)
        # Priority 5: everything else
        return (5, rel)

    return sorted(files, key=_priority)


# ---------------------------------------------------------------------------
# Markdown format builder
# ---------------------------------------------------------------------------

def _build_markdown(
    root: Path,
    project_name: str,
    repo_map: dict,
    all_files: list[Path],
    definitions: dict[str, list[str]],
    include_contents: bool,
    max_tokens: Optional[int],
    compress: bool = False,
) -> str:
    """Build a markdown-formatted LLM context document."""
    parts: list[str] = []

    # --- Header
    parts.append(f"# {project_name} — LLM Context\n")

    # --- Project Overview
    parts.append("## Project Overview\n")
    stack = repo_map.get("tech_stack", [])
    entries = repo_map.get("entry_points", [])
    configs = repo_map.get("config_files", [])
    stats = repo_map.get("stats", {})

    parts.append(f"- **Tech stack**: {', '.join(stack) if stack else 'not detected'}")
    parts.append(f"- **Entry points**: {', '.join(f'`{e}`' for e in entries) if entries else 'none detected'}")
    parts.append(f"- **Config files**: {', '.join(f'`{c}`' for c in configs) if configs else 'none'}")
    parts.append(f"- **Total files**: {stats.get('total_files', len(all_files))}")

    layers = repo_map.get("layers", {})
    if layers:
        parts.append(f"- **Layers**: {', '.join(layers.keys())}")
    parts.append("")

    # --- Directory Tree
    parts.append("## Directory Tree\n")
    parts.append("```")
    parts.append(_build_tree(root, all_files))
    parts.append("```\n")

    # --- Key Definitions
    if definitions:
        parts.append("## Key Definitions\n")
        for file_path in sorted(definitions.keys()):
            defs = definitions[file_path]
            if defs:
                parts.append(f"### `{file_path}`")
                parts.append(", ".join(f"`{d}`" for d in defs))
                parts.append("")

    # --- File Contents
    if include_contents:
        parts.append("## File Contents\n")
        ordered = _prioritize_files(all_files, root, repo_map)

        budget_chars = max_tokens * _CHARS_PER_TOKEN if max_tokens else None
        # Reserve ~20% of budget for the sections above
        header_text = "\n".join(parts)
        used_chars = len(header_text)

        compression_stats_total = {"original": 0, "compressed": 0}

        for f in ordered:
            try:
                rel = str(f.relative_to(root))
            except ValueError:
                continue
            try:
                content = f.read_text(errors="replace")
            except OSError:
                continue

            # Apply compression if requested
            display_content = content
            if compress and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                display_content = _compress_content(content, rel)
                compression_stats_total["original"] += len(content)
                compression_stats_total["compressed"] += len(display_content)

            # Build file section
            lang = _ext_to_lang_hint(f.suffix.lower())
            section = f"### `{rel}`\n\n```{lang}\n{display_content}\n```\n"

            # Check budget
            if budget_chars is not None:
                if used_chars + len(section) > budget_chars:
                    parts.append(f"<!-- Token budget reached. {len(ordered) - ordered.index(f)} files omitted. -->\n")
                    break
                used_chars += len(section)

            parts.append(section)

        # Add compression stats if compression was used
        if compress and compression_stats_total["original"] > 0:
            orig_tok = compression_stats_total["original"] // _CHARS_PER_TOKEN
            comp_tok = compression_stats_total["compressed"] // _CHARS_PER_TOKEN
            reduction = (1.0 - comp_tok / max(orig_tok, 1)) * 100
            parts.append(
                f"<!-- Compression: {orig_tok:,} -> {comp_tok:,} tokens "
                f"({reduction:.0f}% reduction) -->\n"
            )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# XML format builder (CXML-style, like rendergit)
# ---------------------------------------------------------------------------

def _build_xml(
    root: Path,
    project_name: str,
    repo_map: dict,
    all_files: list[Path],
    definitions: dict[str, list[str]],
    include_contents: bool,
    max_tokens: Optional[int],
    compress: bool = False,
) -> str:
    """Build an XML-formatted LLM context document (CXML-style)."""
    parts: list[str] = []

    parts.append(f'<repository name="{_xml_escape(project_name)}">')

    # --- Overview
    stack = repo_map.get("tech_stack", [])
    entries = repo_map.get("entry_points", [])
    configs = repo_map.get("config_files", [])
    stats = repo_map.get("stats", {})

    parts.append("  <overview>")
    parts.append(f"    <tech_stack>{', '.join(stack)}</tech_stack>")
    parts.append(f"    <entry_points>{', '.join(entries)}</entry_points>")
    parts.append(f"    <config_files>{', '.join(configs)}</config_files>")
    parts.append(f"    <total_files>{stats.get('total_files', len(all_files))}</total_files>")
    parts.append("  </overview>")

    # --- Tree
    parts.append("  <tree>")
    parts.append(_indent(_build_tree(root, all_files), 4))
    parts.append("  </tree>")

    # --- Definitions
    if definitions:
        parts.append("  <definitions>")
        for file_path in sorted(definitions.keys()):
            defs = definitions[file_path]
            if defs:
                parts.append(f'    <file path="{_xml_escape(file_path)}">')
                for d in defs:
                    parts.append(f"      <def>{_xml_escape(d)}</def>")
                parts.append("    </file>")
        parts.append("  </definitions>")

    # --- File contents
    if include_contents:
        parts.append("  <files>")
        ordered = _prioritize_files(all_files, root, repo_map)

        budget_chars = max_tokens * _CHARS_PER_TOKEN if max_tokens else None
        header_text = "\n".join(parts)
        used_chars = len(header_text)

        for f in ordered:
            try:
                rel = str(f.relative_to(root))
            except ValueError:
                continue
            try:
                content = f.read_text(errors="replace")
            except OSError:
                continue

            # Apply compression if requested
            display_content = content
            if compress and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                display_content = _compress_content(content, rel)

            section = f'    <file path="{_xml_escape(rel)}">\n{_xml_escape(display_content)}\n    </file>'

            if budget_chars is not None:
                if used_chars + len(section) > budget_chars:
                    parts.append("    <!-- Token budget reached. -->")
                    break
                used_chars += len(section)

            parts.append(section)

        parts.append("  </files>")

    parts.append("</repository>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ext_to_lang_hint(ext: str) -> str:
    """Map file extension to markdown code fence language hint."""
    mapping = {
        ".py": "python", ".ts": "typescript", ".tsx": "tsx",
        ".js": "javascript", ".jsx": "jsx", ".go": "go",
        ".rs": "rust", ".java": "java", ".rb": "ruby",
        ".cs": "csharp", ".cpp": "cpp", ".c": "c", ".h": "c",
        ".php": "php", ".swift": "swift", ".kt": "kotlin",
        ".md": "markdown", ".json": "json", ".yaml": "yaml",
        ".yml": "yaml", ".toml": "toml", ".xml": "xml",
        ".html": "html", ".css": "css", ".scss": "scss",
        ".sql": "sql", ".sh": "bash", ".bash": "bash",
        ".graphql": "graphql", ".proto": "protobuf",
    }
    return mapping.get(ext, "")


def _xml_escape(text: str) -> str:
    """Escape XML special characters."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _indent(text: str, spaces: int) -> str:
    """Indent each line of text by N spaces."""
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.split("\n"))


def _compress_content(content: str, file_path: str) -> str:
    """Compress file content using intelligence compressor if available.

    Falls back to first-N-lines extraction if tree-sitter is not available.
    """
    try:
        from .intelligence.compressor import compress_file
        return compress_file(content, file_path)
    except ImportError:
        # Intelligence module not available — fallback to first 30 lines
        lines = content.split("\n")
        if len(lines) <= 30:
            return content
        return "\n".join(lines[:30]) + f"\n# ... ({len(lines) - 30} more lines)"
