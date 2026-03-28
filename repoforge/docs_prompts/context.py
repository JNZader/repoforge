"""Repo context formatting helpers for prompt construction."""

from __future__ import annotations

from collections import defaultdict


def _format_stack(tech_stack: list[str]) -> str:
    return ", ".join(tech_stack) if tech_stack else "not detected"


def _format_layers(layers: dict) -> str:
    if not layers:
        return "  (no layers detected)"
    lines = []
    for name, data in layers.items():
        mod_count = len(data.get("modules", []))
        lines.append(f"  - **{name}** (`{data['path']}`) — {mod_count} modules")
    return "\n".join(lines)


def _format_modules(layers: dict, max_per_layer: int = 30) -> str:
    lines = []
    for layer_name, layer_data in layers.items():
        modules = layer_data.get("modules", [])[:max_per_layer]
        if not modules:
            continue
        lines.append(f"\n  [{layer_name}]")
        for m in modules:
            exports = ", ".join(m.get("exports", [])[:5])
            hint = m.get("summary_hint", "")[:80]
            line = f"    - `{m['path']}` ({m['language']})"
            if hint:
                line += f" — {hint}"
            if exports:
                line += f" | exports: {exports}"
            lines.append(line)
    return "\n".join(lines) if lines else "  (no modules detected)"


def _build_directory_tree(repo_map: dict, max_depth: int = 4) -> str:
    """Build a full directory tree from ALL module paths in the repo map.

    This ensures the LLM sees every directory in the project, not just
    the ones that happened to be in the first N modules of a layer.
    Also includes directories discovered by the build parser (packages).
    """
    # Collect all file paths from all layers
    all_paths: list[str] = []
    for layer_data in repo_map.get("layers", {}).values():
        for mod in layer_data.get("modules", []):
            path = mod.get("path", "")
            if path:
                all_paths.append(path)

    # Also include paths from build_info.packages if available
    # (these are directory paths like "internal/store")
    # build_info in repo_map is a flat dict, packages are already merged
    # into layers by _merge_build_packages, but let's also include
    # the full_directory_tree field if present
    for path in repo_map.get("_all_directories", []):
        all_paths.append(path + "/.placeholder")

    if not all_paths:
        return "  (no files detected)"

    # Build tree structure: {dir_path: set of filenames}
    tree: dict[str, set[str]] = defaultdict(set)
    all_dirs: set[str] = set()

    for path in all_paths:
        parts = path.split("/")
        # Add the file to its parent directory
        if len(parts) > 1:
            parent = "/".join(parts[:-1])
            tree[parent].add(parts[-1])
            # Register all intermediate directories
            for i in range(1, len(parts)):
                dir_path = "/".join(parts[:i])
                all_dirs.add(dir_path)
                if i > 1:
                    parent_dir = "/".join(parts[:i - 1])
                    tree[parent_dir].add(parts[i - 1] + "/")
        else:
            tree["."].add(parts[0])

    # Render as indented tree
    lines = ["```"]

    def render_dir(prefix: str, dir_path: str, indent: int):
        if indent > max_depth:
            return
        entries = sorted(tree.get(dir_path, set()))
        # Separate dirs and files
        dirs = [e.rstrip("/") for e in entries if e.endswith("/")]
        files = [e for e in entries if not e.endswith("/") and not e.endswith(".placeholder")]

        for d in dirs:
            child_path = f"{dir_path}/{d}" if dir_path != "." else d
            child_files = tree.get(child_path, set())
            # Count non-placeholder files
            real_files = [f for f in child_files if not f.endswith(".placeholder")]
            child_dirs = [e.rstrip("/") for e in child_files if e.endswith("/")]
            lines.append(f"{prefix}{d}/")
            render_dir(prefix + "  ", child_path, indent + 1)

        for f in files:
            lines.append(f"{prefix}{f}")

    # Start from root-level directories
    root_entries: set[str] = set()
    for path in all_paths:
        top = path.split("/")[0]
        if "/" in path:
            root_entries.add(top + "/")
        else:
            root_entries.add(top)

    for entry in sorted(root_entries):
        if entry.endswith("/"):
            dir_name = entry.rstrip("/")
            lines.append(f"{dir_name}/")
            render_dir("  ", dir_name, 1)
        else:
            if not entry.endswith(".placeholder"):
                lines.append(entry)

    lines.append("```")
    return "\n".join(lines)


def _format_entry_points(entry_points: list[str]) -> str:
    return ", ".join(f"`{e}`" for e in entry_points) if entry_points else "none detected"


def _format_config_files(config_files: list[str]) -> str:
    return ", ".join(f"`{c}`" for c in config_files) if config_files else "none"


def _repo_context(repo_map: dict, graph_context: str = "") -> str:
    """Build the shared repo context block used in all prompts.

    Args:
        graph_context: Optional dependency analysis from graph v2.
    """
    ctx = f"""
## Repo context (from static analysis — use this as your source of truth)

- **Tech stack**: {_format_stack(repo_map.get("tech_stack", []))}
- **Entry points**: {_format_entry_points(repo_map.get("entry_points", []))}
- **Config files**: {_format_config_files(repo_map.get("config_files", []))}
- **Total files scanned**: {repo_map.get("stats", {}).get("total_files", "?")}

### Full Project Structure
{_build_directory_tree(repo_map)}

### Layers detected
{_format_layers(repo_map.get("layers", {}))}

### Key modules by layer
{_format_modules(repo_map.get("layers", {}))}
"""
    if graph_context:
        ctx += f"\n{graph_context}\n"
    return ctx


def _repo_context_light(repo_map: dict, graph_context: str = "") -> str:
    """Build a lighter repo context — directory tree + layers, NO per-module listing.

    Used when pre-digested chunks (module summaries) replace the verbose module list.
    Saves ~40-60% of tokens compared to _repo_context.
    """
    ctx = f"""
## Repo context (from static analysis — use this as your source of truth)

- **Tech stack**: {_format_stack(repo_map.get("tech_stack", []))}
- **Entry points**: {_format_entry_points(repo_map.get("entry_points", []))}
- **Config files**: {_format_config_files(repo_map.get("config_files", []))}
- **Total files scanned**: {repo_map.get("stats", {}).get("total_files", "?")}

### Full Project Structure
{_build_directory_tree(repo_map)}

### Layers detected
{_format_layers(repo_map.get("layers", {}))}
"""
    if graph_context:
        ctx += f"\n{graph_context}\n"
    return ctx


def _repo_context_facts_only(repo_map: dict, graph_context: str = "") -> str:
    """Ultra-light repo context for facts-only mode — NO tree, NO modules.

    Only emits tech stack, entry points, and layer summary.
    Config files omitted — facts carry that info.
    """
    ctx = f"""
## Repo context
- **Tech stack**: {_format_stack(repo_map.get("tech_stack", []))}
- **Entry points**: {_format_entry_points(repo_map.get("entry_points", []))}

### Layers
{_format_layers(repo_map.get("layers", {}))}
"""
    if graph_context:
        ctx += f"\n{graph_context}\n"
    return ctx
