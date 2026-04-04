"""Chapter prompt builders — index, overview, quickstart, architecture."""

from __future__ import annotations

from .context import (
    _format_stack,
    _repo_context,
    _repo_context_light,
)
from .system import _base_system, _base_system_facts_only

# ---------------------------------------------------------------------------
# Chapter 0: index.md — Navigation hub
# ---------------------------------------------------------------------------

def index_prompt(repo_map: dict, language: str, project_name: str, chapters: list[dict],
                 graph_context: str = "",
                 facts_only: bool = False) -> tuple[str, str]:
    """
    chapters: [{"file": "01-overview.md", "title": "Overview", "description": "..."}, ...]
    """
    nav_table = "\n".join(
        f"| [{c['title']}]({c['file']}) | {c['description']} |"
        for c in chapters
    )

    if facts_only:
        # Ultra-minimal index: navigation hub needs almost zero context.
        stack_line = _format_stack(repo_map.get("tech_stack", []))
        system = f"Generate a markdown navigation page in **{language}**. Start with `#` heading."
        user = f"""**index.md** for **{project_name}** ({stack_line}).

| Chapter | Description |
|---------|-------------|
{nav_table}

Create: `# {project_name}` heading, brief description, navigation table linking all chapters. Under 50 lines.
"""
        return system, user

    user = f"""Generate the **index.md** (home page) for the documentation of **{project_name}**.

{_repo_context(repo_map, graph_context=graph_context)}

## Chapters to link (generate a navigation table)
| Chapter | Description |
|---------|-------------|
{nav_table}

## What this document must contain
1. `# {project_name}` — main heading with a 2-3 sentence project description derived from the tech stack and entry points.
2. **Quick badges row** — tech stack as inline code badges: `Python` `FastAPI` `React` etc.
3. **Documentation map** — a Markdown table linking all chapters with short descriptions.
4. **Project structure** — a brief directory tree of the detected layers (not every file, just top-level structure).
5. **Quick start snippet** — the single most important command to run this project (infer from entry points and config).

Keep it under 80 lines. It's a navigation page, not a full reference.
Language: {language}
"""
    return _base_system(language), user


# ---------------------------------------------------------------------------
# Chapter 1: 01-overview.md — Tech stack & structure
# ---------------------------------------------------------------------------

def overview_prompt(repo_map: dict, language: str, project_name: str,
                    graph_context: str = "",
                    doc_chunks: dict | None = None) -> tuple[str, str]:
    chunks = doc_chunks or {}
    # Build extension breakdown
    by_ext = repo_map.get("stats", {}).get("by_extension", {})
    ext_lines = "\n".join(f"  - `{ext}`: {count} files" for ext, count in sorted(by_ext.items(), key=lambda x: -x[1])[:10])

    # When chunks are available, use lighter context (no full module list,
    # no graph context) to avoid hitting token limits on small models.
    # Module summaries replace both the verbose listing AND the API surface.
    module_summaries = chunks.get("module_summaries", "")
    if module_summaries:
        # Lighter context: just stack + structure + layers (no per-module listing, no graph)
        ctx = _repo_context_light(repo_map)
        focused_section = f"""
### Module API Summaries (from AST — use these EXACT names)
{module_summaries}
"""
    else:
        ctx = _repo_context(repo_map, graph_context=graph_context)
        focused_section = ""

    user = f"""Generate **01-overview.md** — the technical overview chapter for **{project_name}**.

{ctx}

### File breakdown by extension
{ext_lines or "  (not available)"}
{focused_section}
## What this document must contain
1. `# Project Overview` heading
2. **Tech stack table** — a Markdown table with columns: Technology | Role | Version/Notes.
   Derive roles from what you know about each technology (e.g. React = Frontend UI, FastAPI = REST API).
   Only include technologies confirmed in the repo map.
3. **Project structure** — annotated directory tree. One line per layer/directory with what it contains.
   Use a fenced code block with tree-style indentation.
4. **Entry points** — explain each detected entry point: what it starts, how to invoke it.
5. **Configuration files** — list each config file and its purpose.
6. **Key dependencies** — table of the most important external packages per layer (from imports in modules).

Be specific. Use actual paths. No generic descriptions.
Language: {language}
"""
    return _base_system(language), user


# ---------------------------------------------------------------------------
# Chapter 2: 02-quickstart.md — Installation & first run
# ---------------------------------------------------------------------------

def quickstart_prompt(repo_map: dict, language: str, project_name: str,
                      graph_context: str = "",
                      doc_chunks: dict | None = None) -> tuple[str, str]:
    chunks = doc_chunks or {}
    stack = repo_map.get("tech_stack", [])
    has_python = "Python" in stack
    has_node = "Node.js" in stack
    has_docker = "Docker" in stack
    has_go = "Go" in stack

    hints = []
    if has_python:
        hints.append("Python project: likely needs pip install / venv setup")
    if has_node:
        hints.append("Node.js project: likely needs npm install / yarn")
    if has_docker:
        hints.append("Docker detected: probably has docker-compose.yml")
    if has_go:
        hints.append("Go project: likely needs go mod download + go run/build")

    # Focused context: only CLI commands and env vars
    focused_section = ""
    cli_chunk = chunks.get("cli_commands", "")
    if cli_chunk:
        focused_section = f"""
### Extracted CLI & Environment Data (from source code — use these EXACT values)
{cli_chunk}
"""

    user = f"""Generate **02-quickstart.md** — the Quick Start guide for **{project_name}**.

{_repo_context(repo_map, graph_context=graph_context)}

### Setup hints (inferred from stack)
{chr(10).join(f"- {h}" for h in hints) or "- Infer from entry points and config files"}
{focused_section}
## What this document must contain
1. `# Quick Start` heading
2. **Prerequisites** — list what needs to be installed before starting (infer from tech stack).
   Include version requirements if detectable from config files.
3. **Installation steps** — numbered, copy-pasteable commands. One step = one code block.
   Include: clone, install deps, configure env vars (from .env.example if present).
4. **Running the project** — how to start each layer/service.
   If Docker detected, include docker-compose instructions.
   If multiple entry points, explain each.
5. **Verify it works** — what to check to confirm it's running (URL, output, command).
6. **Common issues** — 2-3 most likely setup problems and their fixes.

All code blocks must have language tags (```bash, ```python, etc.).
Keep commands realistic — infer from actual entry points detected.
Language: {language}
"""
    return _base_system(language), user


# ---------------------------------------------------------------------------
# Chapter 3: 03-architecture.md — Architecture & design
# ---------------------------------------------------------------------------

def architecture_prompt(repo_map: dict, language: str, project_name: str,
                        graph_context: str = "",
                        doc_chunks: dict | None = None,
                        facts_only: bool = False,
                        diagram_context: str = "") -> tuple[str, str]:
    chunks = doc_chunks or {}
    layers = repo_map.get("layers", {})
    layer_names = list(layers.keys())
    is_monorepo = len(layers) > 1

    if facts_only:
        # Ultra-compact: short graph + facts only (no API surface, no sigs).
        # Total system+user must stay under 7K tokens.
        layer_hint = "Monorepo: " + ", ".join(layer_names) if is_monorepo else (layer_names[0] if layer_names else "main")
        user = f"""**03-architecture.md** for **{project_name}** ({layer_hint}, {len(layers)} layer(s)).

{graph_context}

Describe the project architecture: layers, data flow, key design decisions. Use facts provided. No Mermaid.
Language: {language}
"""
        return _base_system_facts_only(language), user

    # Full prompt: rich context with Mermaid diagrams
    arch_chunk = chunks.get("architecture", "")
    focused_section = ""
    if arch_chunk:
        focused_section = f"""
### Pre-digested Architecture Data (from static analysis)
{arch_chunk}
"""

    # Inject auto-generated diagrams if available
    diagram_section = ""
    if diagram_context:
        diagram_section = f"""
### Auto-generated Architecture Diagrams (from code analysis)
Use these diagrams in your output — they are derived from actual import/export analysis.
You may adjust labels for readability but keep the structure accurate.

{diagram_context}
"""

    user = f"""Generate **03-architecture.md** — the Architecture chapter for **{project_name}**.

{_repo_context(repo_map, graph_context=graph_context)}

### Architecture hints
- {"Monorepo with multiple layers: " + ", ".join(layer_names) if is_monorepo else "Single-layer project: " + (layer_names[0] if layer_names else "main")}
- Layers detected: {len(layers)}
{focused_section}{diagram_section}
## What this document must contain
1. `# Architecture` heading
2. **Architecture overview** — 3-5 sentences describing the overall design pattern
   (e.g. "This is a monorepo with a React frontend and a FastAPI backend...").
3. **Architecture diagram** — a Mermaid diagram showing how layers/services interact.
   Use `graph TD` or `graph LR` style. Show data flow between layers.
   Example:
   ```mermaid
   graph LR
     Frontend --> API
     API --> Database
   ```
4. **Layer breakdown** — for each layer: purpose, key responsibilities, technologies used.
   Use a subsection `## Layer: <layer-name>` per layer (one per detected layer).
5. **Data flow** — describe how a typical request flows through the system end-to-end.
   Use a Mermaid sequence diagram if there are multiple layers.
6. **Key design decisions** — bullet list of architectural choices and their rationale
   (infer from tech stack: why React vs Vue? why FastAPI? monorepo structure, etc.)
7. **Inter-layer dependencies** — what each layer imports/calls from others.

Base everything on the actual layers and modules detected. Don't invent services.
Language: {language}
"""
    return _base_system(language), user
