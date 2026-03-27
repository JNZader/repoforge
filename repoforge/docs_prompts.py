"""
docs_prompts.py - Prompt templates for technical documentation generation.

Design philosophy:
- Each chapter gets ONE focused prompt with the scanner's structured context
- We pass concrete facts (exports, imports, stack) so the LLM doesn't hallucinate
- Temperature=0 for reproducibility
- Language-aware: all output in the requested language

Chapters generated:
  index.md          - Overview + navigation hub
  01-overview.md    - Tech stack, project structure, entry points
  02-quickstart.md  - Installation, setup, first run
  03-architecture.md - Architecture decisions, layers, data flow
  04-core-mechanisms.md - Deep dive into key modules/logic
  05-data-models.md - Data structures, schemas, models (if detected)
  06-api-reference.md - Public API / endpoints (if detected)
  07-dev-guide.md   - How to contribute, conventions, add features
"""


# ---------------------------------------------------------------------------
# Shared system prompt — injected in every chapter call
# ---------------------------------------------------------------------------

def _base_system(language: str) -> str:
    return f"""\
You are a senior technical writer generating professional documentation for a software project.

CRITICAL RULES:
1. Write EVERYTHING in **{language}**. Titles, body text, code comments, diagram labels — all in {language}.
2. NEVER invent information. Only describe what is confirmed by the repo map provided.
3. Use concrete names from the repo map (actual file paths, function names, class names).
4. Use Markdown formatting: headers, code blocks, tables, bullet lists.
5. Include Mermaid diagrams where they add clarity (architecture, data flow, sequences).
6. Be concise but complete. Avoid padding. No generic filler sentences.
7. Output ONLY the Markdown content. No preamble, no "here is your document".
8. Start directly with the `#` heading of the document.
9. TECH STACK — STRICT RULE: Use ONLY the technologies explicitly listed in the "Tech stack"
   field of the repo context. Do NOT infer technologies from function names, variable names,
   or export names. If a function is named `make_fastapi_example()` that does NOT mean
   FastAPI is in the stack. If stack says ["Python"], document ONLY Python.
10. EXTRACTED FACTS — STRICT RULE: When an "Extracted Facts" section is provided, use the
    EXACT values from it for port numbers, endpoints, environment variables, database tables,
    CLI commands, and version strings. Do NOT guess or fabricate these values. If the facts
    say port 7437, write 7437 — not 8080, not 3000. If the facts list specific endpoints,
    use those exact paths. Facts are extracted from source code and are authoritative.
11. API SURFACE — CRITICAL RULE: When an "API Surface" section is provided, it contains REAL
    function signatures extracted from the source code via AST parsing. You MUST use these exact
    function names, parameter types, and return types in any code examples. Do NOT invent
    function names or signatures that are not listed in the API Surface. If a function is not
    in the API Surface, do NOT reference it in code examples. The API Surface also lists real
    CLI commands and MCP tools when detected — use those exact names.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _format_modules(layers: dict, max_per_layer: int = 8) -> str:
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

### Layers detected
{_format_layers(repo_map.get("layers", {}))}

### Key modules by layer
{_format_modules(repo_map.get("layers", {}))}
"""
    if graph_context:
        ctx += f"\n{graph_context}\n"
    return ctx


# ---------------------------------------------------------------------------
# Chapter 0: index.md — Navigation hub
# ---------------------------------------------------------------------------

def index_prompt(repo_map: dict, language: str, project_name: str, chapters: list[dict],
                 graph_context: str = "") -> tuple[str, str]:
    """
    chapters: [{"file": "01-overview.md", "title": "Overview", "description": "..."}, ...]
    """
    nav_table = "\n".join(
        f"| [{c['title']}]({c['file']}) | {c['description']} |"
        for c in chapters
    )

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
                    graph_context: str = "") -> tuple[str, str]:
    # Build extension breakdown
    by_ext = repo_map.get("stats", {}).get("by_extension", {})
    ext_lines = "\n".join(f"  - `{ext}`: {count} files" for ext, count in sorted(by_ext.items(), key=lambda x: -x[1])[:10])

    user = f"""Generate **01-overview.md** — the technical overview chapter for **{project_name}**.

{_repo_context(repo_map, graph_context=graph_context)}

### File breakdown by extension
{ext_lines or "  (not available)"}

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
                      graph_context: str = "") -> tuple[str, str]:
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

    user = f"""Generate **02-quickstart.md** — the Quick Start guide for **{project_name}**.

{_repo_context(repo_map, graph_context=graph_context)}

### Setup hints (inferred from stack)
{chr(10).join(f"- {h}" for h in hints) or "- Infer from entry points and config files"}

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
                        graph_context: str = "") -> tuple[str, str]:
    layers = repo_map.get("layers", {})
    layer_names = list(layers.keys())
    is_monorepo = len(layers) > 1

    user = f"""Generate **03-architecture.md** — the Architecture chapter for **{project_name}**.

{_repo_context(repo_map, graph_context=graph_context)}

### Architecture hints
- {"Monorepo with multiple layers: " + ", ".join(layer_names) if is_monorepo else "Single-layer project: " + (layer_names[0] if layer_names else "main")}
- Layers detected: {len(layers)}

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


# ---------------------------------------------------------------------------
# Chapter 4: 04-core-mechanisms.md — Deep dive
# ---------------------------------------------------------------------------

def core_mechanisms_prompt(repo_map: dict, language: str, project_name: str,
                           graph_context: str = "") -> tuple[str, str]:
    # Pick the most interesting modules across all layers
    top_modules = []
    for layer_name, layer_data in repo_map.get("layers", {}).items():
        modules = layer_data.get("modules", [])
        # Take top 3 per layer that have exports
        interesting = [m for m in modules if m.get("exports")][:3]
        for m in interesting:
            top_modules.append((layer_name, m))

    modules_detail = ""
    for layer_name, m in top_modules[:8]:
        exports = ", ".join(m.get("exports", [])[:8])
        imports = ", ".join(m.get("imports", [])[:5])
        hint = m.get("summary_hint", "")
        modules_detail += f"""
  - `{m['path']}` [{layer_name}] ({m['language']})
    Summary: {hint or "no docstring"}
    Exports: {exports or "none"}
    Dependencies: {imports or "none"}"""

    user = f"""Generate **04-core-mechanisms.md** — the Core Mechanisms deep-dive for **{project_name}**.

{_repo_context(repo_map, graph_context=graph_context)}

### Most interesting modules (analyze these in depth)
{modules_detail or "  (use modules from repo context above)"}

## What this document must contain
1. `# Core Mechanisms` heading
2. **Introduction** — what are the 2-4 most important workflows/flows in this system?
   (infer from entry points, key exports, and module names)
3. **For each core mechanism** — create a subsection `## Mechanism N: [Name]` with:
   a. **What it does** — 2-3 sentences
   b. **Key components** — which modules/files are involved (use actual paths)
   c. **Flow diagram** — Mermaid sequence or flowchart diagram
   d. **Key code pattern** — show the pattern used (e.g. how auth works, how a request is handled)
      Use a code block with the LANGUAGE of that file, showing a representative pattern.
      Base it on the actual exports and imports — don't invent function bodies.
   e. **Integration points** — what other modules does this interact with
4. **Cross-cutting concerns** — error handling, logging, config patterns observed across modules.

Focus on depth over breadth. 2-3 mechanisms analyzed well > 6 mechanisms analyzed superficially.
Language: {language}
"""
    return _base_system(language), user


# ---------------------------------------------------------------------------
# Chapter 5: 05-data-models.md — Data structures
# ---------------------------------------------------------------------------

def data_models_prompt(repo_map: dict, language: str, project_name: str,
                       graph_context: str = "") -> tuple[str, str]:
    # Find modules that likely define models
    model_modules = []
    for layer_name, layer_data in repo_map.get("layers", {}).items():
        for m in layer_data.get("modules", []):
            name_lower = m["name"].lower()
            path_lower = m["path"].lower()
            imports_lower = [i.lower() for i in m.get("imports", [])]
            exports = m.get("exports", [])

            is_model = (
                any(kw in name_lower for kw in ("model", "schema", "entity", "type", "interface"))
                or any(kw in path_lower for kw in ("/models/", "/schemas/", "/entities/", "/types/"))
                or any(kw in imports_lower for kw in ("pydantic", "sqlalchemy", "prisma", "typeorm", "mongoose", "zod"))
                or any(e[0].isupper() for e in exports)  # PascalCase = likely classes/types
            )
            if is_model:
                model_modules.append((layer_name, m))

    if not model_modules:
        # Fall back to any modules with PascalCase exports
        for layer_name, layer_data in repo_map.get("layers", {}).items():
            for m in layer_data.get("modules", []):
                if any(e[0].isupper() for e in m.get("exports", [])):
                    model_modules.append((layer_name, m))

    modules_text = ""
    for layer_name, m in model_modules[:8]:
        exports = ", ".join(m.get("exports", [])[:10])
        imports = ", ".join(m.get("imports", [])[:5])
        modules_text += f"\n  - `{m['path']}` [{layer_name}]: exports={exports}, uses={imports}"

    user = f"""Generate **05-data-models.md** — the Data Models chapter for **{project_name}**.

{_repo_context(repo_map, graph_context=graph_context)}

### Modules likely containing data models/schemas
{modules_text or "  (infer from modules with PascalCase exports or ORM imports)"}

## What this document must contain
1. `# Data Models` heading
2. **Overview** — what data modeling approach is used (Pydantic, SQLAlchemy, Prisma, TypeScript interfaces, etc.)
   Infer from imports detected in model modules.
3. **For each key model/schema** — create `## ModelName` subsections with:
   a. **Purpose** — what this model represents in the domain
   b. **Fields** — table with columns: Field | Type | Description (infer from exports and context)
   c. **Relationships** — how it relates to other models (if detectable)
4. **Data flow diagram** — a simple Mermaid ER diagram or class diagram if multiple models exist.
5. **Validation rules** — any validation patterns detected (Pydantic validators, Zod schemas, etc.)

If no clear models are detected, document the key data structures used in the main modules.
Be honest: mark fields as "inferred" if not explicitly visible in exports.
Language: {language}
"""
    return _base_system(language), user


# ---------------------------------------------------------------------------
# Chapter 6: 06-api-reference.md — Public API / endpoints
# ---------------------------------------------------------------------------

def api_reference_prompt(repo_map: dict, language: str, project_name: str,
                         graph_context: str = "") -> tuple[str, str]:
    # Find API-related modules
    api_modules = []
    for layer_name, layer_data in repo_map.get("layers", {}).items():
        for m in layer_data.get("modules", []):
            name_lower = m["name"].lower()
            path_lower = m["path"].lower()
            imports_lower = [i.lower() for i in m.get("imports", [])]
            exports = m.get("exports", [])

            is_api = (
                any(kw in name_lower for kw in ("router", "route", "endpoint", "controller", "handler", "api", "view"))
                or any(kw in path_lower for kw in ("/routes/", "/endpoints/", "/controllers/", "/handlers/", "/api/", "/views/"))
                or any(kw in imports_lower for kw in ("fastapi", "express", "flask", "django", "hono", "gin", "axum", "spring"))
            )
            if is_api:
                api_modules.append((layer_name, m))

    modules_text = ""
    for layer_name, m in api_modules[:10]:
        exports = ", ".join(m.get("exports", [])[:10])
        hint = m.get("summary_hint", "")
        modules_text += f"\n  - `{m['path']}` [{layer_name}]: {hint} | exports: {exports}"

    user = f"""Generate **06-api-reference.md** — the API Reference for **{project_name}**.

{_repo_context(repo_map, graph_context=graph_context)}

### Modules likely containing API endpoints/routes
{modules_text or "  (infer from modules with router/handler naming patterns)"}

## What this document must contain
1. `# API Reference` heading
2. **API overview** — base URL pattern, authentication method (infer from imports: JWT, OAuth, etc.),
   response format (JSON, etc.)
3. **Endpoint groups** — organize by module/router. For each group, a subsection `## /resource-name`.
4. **For each endpoint** (infer from exported function names):
   - Method + path: `GET /users` (infer path from function name: `get_users` → `GET /users`)
   - Description: what it does (from function name + hint)
   - Request: parameters/body (if inferrable)
   - Response: structure (if inferrable from models)
   - Example: a curl or fetch snippet

IMPORTANT: Be transparent. If you cannot determine exact paths/parameters from static analysis,
say "Path inferred from function name" and mark uncertain fields. Do NOT invent endpoint details.
Language: {language}
"""
    return _base_system(language), user


# ---------------------------------------------------------------------------
# Chapter 7: 07-dev-guide.md — Development guide
# ---------------------------------------------------------------------------

def dev_guide_prompt(repo_map: dict, language: str, project_name: str,
                     graph_context: str = "") -> tuple[str, str]:
    layers = repo_map.get("layers", {})

    user = f"""Generate **07-dev-guide.md** — the Developer Guide for **{project_name}**.

{_repo_context(repo_map, graph_context=graph_context)}

## What this document must contain
1. `# Developer Guide` heading
2. **Development setup** — how to set up a dev environment (different from prod quickstart if applicable).
   Include: hot reload, debug mode, test runner.
3. **Project conventions** — naming conventions, file organization patterns observed in the codebase.
   Infer from actual module names, directory structure, export patterns.
4. **How to add a new feature** — step-by-step guide for the most common task.
   Make it specific to this project's structure:
   {"- For a monorepo: explain which layer to modify and how layers interact" if len(layers) > 1 else "- For a single-layer project: explain the file structure to follow"}
   Example: "To add a new API endpoint: 1) Create file in X directory 2) Export handler function 3) Register in Y"
5. **Testing** — how to run tests, test file naming conventions, key test patterns detected.
   Infer test runner from config files (pytest, jest, go test, etc.)
6. **Common tasks** — cheat sheet of frequent dev commands:
   | Task | Command |
   |------|---------|
   | Run dev server | ... |
   | Run tests | ... |
   | Build | ... |
   | Lint | ... |
7. **Code style** — any linting/formatting tools detected (ruff, eslint, prettier, etc.).

Be concrete and specific to THIS project. No generic advice.
Language: {language}
"""
    return _base_system(language), user



# ===========================================================================
# PROJECT CLASSIFICATION + ADAPTIVE CHAPTERS
# ===========================================================================
#
# Instead of a fixed chapter set with optional slots, we classify the project
# type and build a tailored chapter list. Every project type gets chapters
# that make sense for IT specifically.
#
# Project types:
#   web_service    → REST API / GraphQL / gRPC backend
#   cli_tool       → Command-line application
#   library_sdk    → Reusable library / SDK / package
#   data_science   → ML / data pipeline / notebooks
#   frontend_app   → SPA / web frontend (React, Vue, Angular, Svelte...)
#   mobile_app     → iOS / Android / React Native / Flutter
#   desktop_app    → Electron / Qt / native desktop
#   infra_devops   → Terraform / Helm / Ansible / Docker Compose
#   monorepo       → Multiple distinct apps in one repo (overrides others)
#   generic        → Fallback — uses the universal chapter set
# ===========================================================================


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def classify_project(repo_map: dict) -> str:
    """
    Classify a project into one of the known types based on structural signals.

    Uses tech_stack, config_files, entry_points, module paths, and file counts.
    Returns a string key like "web_service", "cli_tool", etc.

    Deliberately NOT import-based — works for any language.
    """
    stack       = " ".join(repo_map.get("tech_stack", [])).lower()
    configs     = " ".join(repo_map.get("config_files", [])).lower()
    entries     = " ".join(repo_map.get("entry_points", [])).lower()
    layers      = repo_map.get("layers", {})
    total_files = repo_map.get("stats", {}).get("total_files", 0)

    all_paths = " ".join(
        m["path"].lower()
        for ld in layers.values()
        for m in ld.get("modules", [])
    )
    all_names = " ".join(
        m["name"].lower()
        for ld in layers.values()
        for m in ld.get("modules", [])
    )

    # --- Monorepo: multiple distinct layers (frontend + backend, etc.)
    if len(layers) >= 3:
        return "monorepo"
    has_frontend_layer = any(
        k in ("frontend", "web", "client", "ui") for k in layers
    )
    has_backend_layer = any(
        k in ("backend", "api", "server") for k in layers
    )
    if has_frontend_layer and has_backend_layer:
        return "monorepo"

    # --- Infrastructure / DevOps
    infra_signals = (
        "terraform", "helm", "ansible", "pulumi", "cdk",
        "dockerfile", "docker-compose", ".tf", ".hcl",
        "kubernetes", "k8s",
    )
    if any(s in configs or s in stack or s in all_paths for s in infra_signals):
        return "infra_devops"

    # --- Mobile
    mobile_signals = (
        "react native", "flutter", "expo", "swift", "kotlin",
        "android", "ios", "capacitor", "ionic",
    )
    if any(s in stack for s in mobile_signals):
        return "mobile_app"

    # --- Desktop
    desktop_signals = ("electron", "qt", "gtk", "tauri", "winforms", "wpf", "maui")
    if any(s in stack or s in configs for s in desktop_signals):
        return "desktop_app"

    # --- Data science / ML
    ds_signals = (
        "jupyter", "notebook", "sklearn", "tensorflow", "pytorch",
        "keras", "pandas", "numpy", "mlflow", "hugging", "llm",
        "langchain", "onnx", "spark", "dask",
    )
    ds_paths = ("train", "model", "notebook", "dataset", "pipeline", "experiment")
    if any(s in stack for s in ds_signals):
        return "data_science"
    if any(s in all_paths or s in all_names for s in ds_paths):
        # Only classify as data_science if no clear web signals
        web_counter = sum(1 for s in ("server", "api", "handler", "controller", "route") if s in all_paths)
        if web_counter == 0:
            return "data_science"

    # --- Frontend SPA (no backend layer)
    frontend_signals = (
        "react", "vue", "angular", "svelte", "next.js", "nuxt",
        "vite", "remix", "astro",
    )
    if any(s in stack for s in frontend_signals):
        # If it also has server code it's web_service or monorepo
        if not any(s in all_paths for s in ("server", "api", "handler", "controller")):
            return "frontend_app"

    # --- CLI tool
    cli_signals_stack = ("click", "cobra", "clap", "argparse", "typer", "commander")
    cli_signals_path  = ("cmd", "command", "cli", "bin")
    cli_entry          = ("cli", "cmd", "bin")
    if any(s in stack for s in cli_signals_stack):
        return "cli_tool"
    if any(s in all_paths for s in cli_signals_path):
        # CLI + no web = CLI tool
        if not any(s in all_paths for s in ("server", "handler", "controller", "route")):
            return "cli_tool"
    if any(s in entries for s in cli_entry) and total_files < 20:
        return "cli_tool"

    # --- Library / SDK: no entry points, meant to be imported
    if not entries and total_files < 30:
        # Has exports but no "main" / "server" entry
        if not any(s in all_paths for s in ("server", "api", "handler", "controller")):
            return "library_sdk"

    # --- Web service (default for anything with server signals)
    web_signals = (
        "server", "api", "handler", "controller", "route", "endpoint",
        "middleware", "graphql", "grpc", "rest", "http",
    )
    if any(s in all_paths or s in all_names for s in web_signals):
        return "web_service"

    if any(s in entries for s in ("main", "app", "server", "index")):
        return "web_service"

    # --- Fallback
    return "generic"


# ---------------------------------------------------------------------------
# Adaptive chapter catalog
# Each type specifies which chapters to generate.
# Format: list of chapter dicts with "file", "title", "description", "prompt_fn"
# ---------------------------------------------------------------------------

# Sentinel: chapters common to ALL project types
UNIVERSAL_CHAPTERS = [
    {"file": "index.md",           "title": "Home",          "description": "Project overview and navigation"},
    {"file": "01-overview.md",     "title": "Overview",      "description": "Tech stack, structure, entry points"},
    {"file": "02-quickstart.md",   "title": "Quick Start",   "description": "Installation and first run"},
    {"file": "03-architecture.md", "title": "Architecture",  "description": "Architecture design and data flow"},
    {"file": "07-dev-guide.md",    "title": "Dev Guide",     "description": "Development guide and conventions"},
]

# Project-type-specific chapter additions (injected between 03 and 07)
ADAPTIVE_CHAPTERS: dict[str, list[dict]] = {

    "web_service": [
        {"file": "04-core-mechanisms.md", "title": "Core Mechanisms",  "description": "Request lifecycle, middleware, auth"},
        {"file": "05-data-models.md",     "title": "Data Models",      "description": "Schemas, entities, database design"},
        {"file": "06-api-reference.md",   "title": "API Reference",    "description": "Endpoints, methods, request/response"},
    ],

    "cli_tool": [
        {"file": "04-core-mechanisms.md", "title": "Core Mechanics",   "description": "Execution flow, plugin system"},
        {"file": "05-commands.md",        "title": "Commands",         "description": "All commands, flags, and options"},
        {"file": "06-config.md",          "title": "Configuration",    "description": "Config files, env vars, defaults"},
    ],

    "library_sdk": [
        {"file": "04-core-mechanisms.md", "title": "Core Mechanics",   "description": "Internal design, key abstractions"},
        {"file": "05-api-reference.md",   "title": "Public API",       "description": "Full public API surface"},
        {"file": "06-integration.md",     "title": "Integration Guide","description": "How to use this library in a project"},
    ],

    "data_science": [
        {"file": "04-data-pipeline.md",   "title": "Data Pipeline",    "description": "Data ingestion, transformation, storage"},
        {"file": "05-models.md",          "title": "Models & Training", "description": "Model architecture, training, evaluation"},
        {"file": "06-experiments.md",     "title": "Experiments",      "description": "Experiment tracking, metrics, results"},
    ],

    "frontend_app": [
        {"file": "04-core-mechanisms.md", "title": "Core Mechanics",   "description": "Routing, state management, data fetching"},
        {"file": "05-components.md",      "title": "Components",       "description": "Key UI components and their props"},
        {"file": "06-state.md",           "title": "State Management", "description": "Global state, stores, context"},
    ],

    "mobile_app": [
        {"file": "04-core-mechanisms.md", "title": "Core Mechanics",   "description": "Navigation, lifecycle, permissions"},
        {"file": "05-screens.md",         "title": "Screens & Navigation", "description": "Screen map, navigation flows"},
        {"file": "06-native.md",          "title": "Native Integrations", "description": "Device APIs, push notifications, storage"},
    ],

    "desktop_app": [
        {"file": "04-core-mechanisms.md", "title": "Core Mechanics",   "description": "Window management, IPC, lifecycle"},
        {"file": "05-ui.md",              "title": "UI & Windows",     "description": "Windows, dialogs, UI components"},
        {"file": "06-platform.md",        "title": "Platform Guide",   "description": "Platform-specific behavior, packaging"},
    ],

    "infra_devops": [
        {"file": "04-resources.md",       "title": "Resources",        "description": "Infrastructure resources defined"},
        {"file": "05-variables.md",       "title": "Variables & Config","description": "Input variables, outputs, secrets"},
        {"file": "06-deployment.md",      "title": "Deployment Guide", "description": "How to apply, rollback, environments"},
    ],

    "monorepo": [
        {"file": "04-core-mechanisms.md", "title": "Core Mechanics",   "description": "Shared code, inter-service communication"},
        {"file": "05-data-models.md",     "title": "Data Models",      "description": "Shared schemas and contracts"},
        {"file": "06-api-reference.md",   "title": "API Reference",    "description": "Internal and external API surface"},
        {"file": "06b-service-map.md",    "title": "Service Map",      "description": "How services/layers interact"},
    ],

    "generic": [
        {"file": "04-core-mechanisms.md", "title": "Core Mechanisms",  "description": "Key logic and design patterns"},
        {"file": "05-data-models.md",     "title": "Data Structures",  "description": "Key data structures and types"},
    ],
}


# ---------------------------------------------------------------------------
# Adaptive prompt dispatcher
# Maps chapter file → prompt function (new chapters + existing ones)
# ---------------------------------------------------------------------------

def _dispatch_prompt(chapter_file: str, repo_map: dict, language: str,
                     project_name: str, project_type: str,
                     active_chapters: list[dict],
                     graph_context: str = "") -> tuple[str, str]:
    """Route a chapter file to its prompt function."""

    # Existing prompts (reused across types)
    if chapter_file == "index.md":
        non_index = [c for c in active_chapters if c["file"] != "index.md"]
        return index_prompt(repo_map, language, project_name, non_index, graph_context=graph_context)
    if chapter_file == "01-overview.md":
        return overview_prompt(repo_map, language, project_name, graph_context=graph_context)
    if chapter_file == "02-quickstart.md":
        return quickstart_prompt(repo_map, language, project_name, graph_context=graph_context)
    if chapter_file == "03-architecture.md":
        return architecture_prompt(repo_map, language, project_name, graph_context=graph_context)
    if chapter_file == "04-core-mechanisms.md":
        return core_mechanisms_prompt(repo_map, language, project_name, graph_context=graph_context)
    if chapter_file == "05-data-models.md":
        return data_models_prompt(repo_map, language, project_name, graph_context=graph_context)
    if chapter_file == "06-api-reference.md":
        return api_reference_prompt(repo_map, language, project_name, graph_context=graph_context)
    if chapter_file == "07-dev-guide.md":
        return dev_guide_prompt(repo_map, language, project_name, graph_context=graph_context)

    # Adaptive chapter prompts
    return _adaptive_prompt(chapter_file, repo_map, language, project_name, project_type, graph_context=graph_context)


def _adaptive_prompt(chapter_file: str, repo_map: dict, language: str,
                     project_name: str, project_type: str,
                     graph_context: str = "") -> tuple[str, str]:
    """Generate prompts for project-type-specific chapters."""
    sys = _base_system(language)
    ctx = _repo_context(repo_map, graph_context=graph_context)

    # --- CLI: commands reference
    if chapter_file == "05-commands.md":
        user = f"""Generate **05-commands.md** — the Commands Reference for the CLI tool **{project_name}**.
{ctx}
## What this document must contain
1. `# Commands Reference` heading
2. **Usage pattern** — the general invocation pattern: `tool [global-flags] <command> [flags] [args]`
3. **Global flags** — flags that apply to all commands (--help, --verbose, --config, etc.)
4. **For each command** (infer from exported function names and module names):
   - Syntax: `tool command [flags] <required-arg> [optional-arg]`
   - Description: what it does
   - Flags: table with Flag | Default | Description
   - Example: 1-2 concrete usage examples
5. **Exit codes** — if detectable from the code
6. **Environment variables** — any env vars the CLI reads

Base commands on actual exported function/method names. Mark inferred items clearly.
Language: {language}"""
        return sys, user

    # --- CLI: configuration
    if chapter_file == "06-config.md":
        user = f"""Generate **06-config.md** — the Configuration Reference for **{project_name}**.
{ctx}
## What this document must contain
1. `# Configuration` heading
2. **Configuration sources** — in priority order (CLI flags > env vars > config file > defaults)
3. **Config file** — format (YAML/TOML/JSON/INI), default location, example with all options
4. **Environment variables** — table: Variable | Default | Description
5. **Per-command config** — any command-specific settings
6. **Profiles / environments** — if multiple environments are supported (dev/prod/staging)

Infer from config file names detected and module exports. Language: {language}"""
        return sys, user

    # --- Library: public API
    if chapter_file == "05-api-reference.md" and project_type == "library_sdk":
        user = f"""Generate **05-api-reference.md** — the Public API Reference for the library **{project_name}**.
{ctx}
## What this document must contain
1. `# Public API Reference` heading
2. **Package/module structure** — how the public API is organized
3. **For each public export** (use actual exported names from repo map):
   - Signature with types
   - Description: what it does, when to use it
   - Parameters: table with Name | Type | Required | Description
   - Returns: type and description
   - Example: minimal working code snippet
4. **Error handling** — what exceptions/errors can be raised and when
5. **Deprecation notices** — if any deprecated APIs are detected

Focus on the PUBLIC surface only. Ignore internal/private exports.
Language: {language}"""
        return sys, user

    # --- Library: integration guide
    if chapter_file == "06-integration.md":
        user = f"""Generate **06-integration.md** — the Integration Guide for the library **{project_name}**.
{ctx}
## What this document must contain
1. `# Integration Guide` heading
2. **Installation** — how to add this library as a dependency (pip, npm, cargo, maven, etc.)
3. **Minimal working example** — the simplest possible usage in a code block
4. **Common use cases** — 3-4 typical integration scenarios with code examples
5. **Framework integrations** — if the library works with specific frameworks, show how
6. **Configuration** — any initialization/setup required before using
7. **Testing** — how to mock/stub this library in tests

Language: {language}"""
        return sys, user

    # --- Data science: pipeline
    if chapter_file == "04-data-pipeline.md":
        user = f"""Generate **04-data-pipeline.md** — the Data Pipeline chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Data Pipeline` heading
2. **Pipeline overview** — Mermaid flowchart showing data flow from source to output
3. **Data sources** — what data comes in (files, databases, APIs, streams)
4. **Transformation steps** — each processing stage with:
   - Input/output format
   - Key transformations applied
   - Relevant code module
5. **Data storage** — where processed data is stored
6. **Scheduling / triggers** — how/when the pipeline runs
7. **Data validation** — any quality checks in the pipeline

Language: {language}"""
        return sys, user

    # --- Data science: models & training
    if chapter_file == "05-models.md":
        user = f"""Generate **05-models.md** — the Models & Training chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Models & Training` heading
2. **Model overview** — what problem is being solved, what type of model (classification, regression, etc.)
3. **Architecture** — model structure (layers, hyperparameters if visible in code)
4. **Training process**:
   - How to run training (command/script)
   - Key hyperparameters and their defaults
   - Training data format expected
5. **Evaluation** — metrics used, how to evaluate, expected performance
6. **Inference** — how to use a trained model for prediction
7. **Model artifacts** — where models are saved, format, versioning

Language: {language}"""
        return sys, user

    # --- Data science: experiments
    if chapter_file == "06-experiments.md":
        user = f"""Generate **06-experiments.md** — the Experiments chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Experiments` heading
2. **Experiment tracking** — what tool is used (MLflow, W&B, DVC, custom) if detectable
3. **How to run an experiment** — step by step
4. **Key metrics** — what is being tracked and optimized
5. **Results** — how to view/compare results
6. **Reproducibility** — seeds, environment pinning, data versioning

Language: {language}"""
        return sys, user

    # --- Frontend: components
    if chapter_file == "05-components.md":
        user = f"""Generate **05-components.md** — the Components chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Components` heading
2. **Component architecture** — how components are organized (atomic design, feature-based, etc.)
3. **For each key component** (use exported component names from repo map):
   - Purpose and when to use it
   - Props/inputs: table with Name | Type | Required | Default | Description
   - Events/outputs emitted
   - Usage example (JSX/template snippet)
4. **Shared/base components** vs **feature components** — how they differ
5. **Styling approach** — CSS modules, Tailwind, styled-components, etc.

Language: {language}"""
        return sys, user

    # --- Frontend: state management
    if chapter_file == "06-state.md":
        user = f"""Generate **06-state.md** — the State Management chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# State Management` heading
2. **State architecture** — global vs local state, what library is used (Redux, Zustand, Pinia, etc.)
3. **Store structure** — how state is organized (slices, modules, stores)
4. **For each store/slice** (from exported names):
   - What state it manages
   - Key actions/mutations
   - How to read from it
5. **Data fetching** — how async data is handled (React Query, SWR, store actions, etc.)
6. **State diagram** — Mermaid diagram of key state transitions if applicable

Language: {language}"""
        return sys, user

    # --- Mobile: screens
    if chapter_file == "05-screens.md":
        user = f"""Generate **05-screens.md** — the Screens & Navigation chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Screens & Navigation` heading
2. **Navigation structure** — Mermaid diagram of the screen hierarchy/flow
3. **Navigation library** — React Navigation, Expo Router, Flutter Navigator, etc.
4. **For each key screen** (infer from module names like *Screen, *Page, *View):
   - Purpose
   - Route/path
   - Key data displayed
   - Navigation actions (where it can go)
5. **Deep linking** — if detected
6. **Auth flow** — protected routes, login redirect

Language: {language}"""
        return sys, user

    # --- Mobile: native integrations
    if chapter_file == "06-native.md":
        user = f"""Generate **06-native.md** — the Native Integrations chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Native Integrations` heading
2. **Permissions** — what device permissions are requested and why
3. **Native APIs used** — camera, location, notifications, biometrics, storage, etc.
4. **Push notifications** — setup, payload format, handling
5. **Offline support** — local storage, sync strategy
6. **Platform differences** — iOS vs Android behavior differences if any

Language: {language}"""
        return sys, user

    # --- Desktop: UI & windows
    if chapter_file == "05-ui.md":
        user = f"""Generate **05-ui.md** — the UI & Windows chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# UI & Windows` heading
2. **Window structure** — main window, child windows, dialogs
3. **UI framework** — Electron/React, Qt, GTK, Tauri/Svelte, etc.
4. **Key UI components** — what they do and where they're defined
5. **IPC / communication** — how UI communicates with backend/main process
6. **Theme / styling** — dark mode support, theming system

Language: {language}"""
        return sys, user

    # --- Desktop: platform guide
    if chapter_file == "06-platform.md":
        user = f"""Generate **06-platform.md** — the Platform Guide for **{project_name}**.
{ctx}
## What this document must contain
1. `# Platform Guide` heading
2. **Supported platforms** — Windows / macOS / Linux and their minimum versions
3. **Platform-specific behavior** — things that work differently per OS
4. **Packaging & distribution** — how to build installers/packages per platform
5. **Auto-update** — if implemented, how it works
6. **Native dependencies** — any platform-native requirements

Language: {language}"""
        return sys, user

    # --- Infra: resources
    if chapter_file == "04-resources.md":
        user = f"""Generate **04-resources.md** — the Infrastructure Resources chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Infrastructure Resources` heading
2. **Resource overview** — Mermaid diagram of all infrastructure components and their relationships
3. **For each resource type** (compute, network, storage, database, etc.):
   - What it is
   - Configuration highlights
   - Key settings to know
4. **Environments** — prod / staging / dev differences
5. **Cost considerations** — which resources drive cost

Language: {language}"""
        return sys, user

    # --- Infra: variables
    if chapter_file == "05-variables.md":
        user = f"""Generate **05-variables.md** — the Variables & Configuration chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Variables & Configuration` heading
2. **Input variables** — table: Name | Type | Default | Required | Description
3. **Output values** — what the infra exports for other modules to use
4. **Secrets management** — how sensitive values are handled (vault, SSM, env vars)
5. **Per-environment config** — how to override for different environments
6. **Terraform/Helm/Ansible specifics** — based on what tool is detected

Language: {language}"""
        return sys, user

    # --- Infra: deployment
    if chapter_file == "06-deployment.md":
        user = f"""Generate **06-deployment.md** — the Deployment Guide for **{project_name}**.
{ctx}
## What this document must contain
1. `# Deployment Guide` heading
2. **Prerequisites** — tools needed, access requirements, credentials
3. **First-time setup** — how to initialize/bootstrap from scratch
4. **Deploy to each environment** — step-by-step commands
5. **Rollback procedure** — how to undo a deployment
6. **Drift detection** — how to check if reality matches desired state
7. **CI/CD integration** — how deployments are automated

Language: {language}"""
        return sys, user

    # --- Monorepo: service map
    if chapter_file == "06b-service-map.md":
        user = f"""Generate **06b-service-map.md** — the Service Map for the monorepo **{project_name}**.
{ctx}
## What this document must contain
1. `# Service Map` heading
2. **Service/layer inventory** — table: Service | Language | Purpose | Port/URL
3. **Inter-service communication** — Mermaid diagram of how services call each other
4. **Shared packages** — what code is shared across services and where it lives
5. **Contracts** — API contracts, shared types, event schemas between services
6. **Local development** — how to run all services together (docker-compose, scripts, etc.)
7. **Deployment topology** — how services are deployed together

Language: {language}"""
        return sys, user

    # --- Fallback for unknown chapter files
    user = f"""Generate the documentation chapter **{chapter_file}** for **{project_name}**.
{ctx}
Write a complete, well-structured Markdown document appropriate for this chapter.
Use headers, tables, code blocks, and Mermaid diagrams where helpful.
Language: {language}"""
    return sys, user


# ---------------------------------------------------------------------------
# New main entry point (replaces get_chapter_prompts)
# ---------------------------------------------------------------------------

def get_chapter_prompts(repo_map: dict, language: str, project_name: str,
                        graph_context: str = "",
                        short_graph_context: str = "") -> list[dict]:
    """
    Return the adaptive list of chapters to generate with their prompts.

    Detects project type first, then builds a tailored chapter list.
    Each entry: {"file": str, "title": str, "description": str, "system": str, "user": str}

    Args:
        graph_context: Full dependency analysis for architecture chapter.
        short_graph_context: Short summary for other chapters.
    """
    project_type = classify_project(repo_map)

    # Build chapter list: universal + type-specific
    type_chapters = ADAPTIVE_CHAPTERS.get(project_type, ADAPTIVE_CHAPTERS["generic"])

    # Build ordered chapter list:
    # index.md first, then 01-overview → 03-architecture, then type-specific, then 07-dev-guide
    index_ch = [c for c in UNIVERSAL_CHAPTERS if c["file"] == "index.md"]
    pre_ch   = [c for c in UNIVERSAL_CHAPTERS
                if c["file"].startswith("0") and c["file"] <= "03-z"]
    post_ch  = [c for c in UNIVERSAL_CHAPTERS
                if c["file"].startswith("0") and c["file"] >= "07-"]
    all_chapters = index_ch + pre_ch + type_chapters + post_ch

    # Build prompts for each chapter
    result = []
    for chapter in all_chapters:
        # Architecture chapter gets full graph context, others get short
        ch_graph = graph_context if chapter["file"] == "03-architecture.md" else short_graph_context
        system, user = _dispatch_prompt(
            chapter["file"], repo_map, language, project_name,
            project_type, all_chapters, graph_context=ch_graph
        )
        result.append({
            "file":        chapter["file"],
            "title":       chapter["title"],
            "description": chapter["description"],
            "project_type": project_type,
            "system":      system,
            "user":        user,
        })

    return result


# ===========================================================================
# MONOREPO HIERARCHICAL DOCUMENTATION
# ===========================================================================
#
# For monorepos, we generate a two-level structure:
#
#   docs/
#   ├── index.md              ← monorepo home (links to all layers)
#   ├── 01-overview.md        ← global tech stack, all layers
#   ├── 02-quickstart.md      ← how to run the whole project
#   ├── 03-architecture.md    ← how layers interact
#   ├── 06b-service-map.md    ← inter-service contracts
#   ├── 07-dev-guide.md       ← monorepo-level conventions
#   ├── frontend/             ← per-layer docs (type = frontend_app)
#   │   ├── index.md
#   │   ├── 04-core-mechanisms.md
#   │   ├── 05-components.md
#   │   └── 06-state.md
#   ├── backend/              ← per-layer docs (type = web_service)
#   │   ├── index.md
#   │   ├── 04-core-mechanisms.md
#   │   ├── 05-data-models.md
#   │   └── 06-api-reference.md
#   └── infra/                ← per-layer docs (type = infra_devops)
#       ├── index.md
#       ├── 04-resources.md
#       ├── 05-variables.md
#       └── 06-deployment.md
#
# Each layer is classified independently by classify_layer().
# The output of get_chapter_prompts() for a monorepo is a flat list
# but each chapter has a "subdir" key (e.g. "frontend") which
# docs_generator.py uses to write to the correct subfolder.
# ===========================================================================


def classify_layer(layer_name: str, layer_data: dict, repo_map: dict) -> str:
    """
    Classify a single monorepo layer into a project type.

    Uses the layer's own modules + its name as primary signals.
    Falls back to classify_project() logic but scoped to this layer.
    """
    name_lower  = layer_name.lower()
    modules     = layer_data.get("modules", [])
    stack_all   = " ".join(repo_map.get("tech_stack", [])).lower()

    all_paths = " ".join(m["path"].lower() for m in modules)
    all_langs = " ".join(m.get("language", "") for m in modules).lower()
    num_files = len(modules)

    # --- Layer name hints (most reliable signal)
    frontend_names = ("frontend", "web", "client", "ui", "app", "spa", "portal")
    backend_names  = ("backend", "api", "server", "service", "core", "domain")
    infra_names    = ("infra", "infrastructure", "terraform", "helm", "k8s",
                      "deploy", "ops", "devops", "cloud")
    mobile_names   = ("mobile", "app", "ios", "android", "native")
    cli_names      = ("cli", "cmd", "tool", "bin", "script")
    shared_names   = ("shared", "common", "lib", "libs", "packages",
                      "pkg", "utils", "core", "types")
    data_names     = ("data", "ml", "ai", "model", "train", "notebook",
                      "analytics", "pipeline", "etl")
    docs_names     = ("docs", "documentation", "wiki")

    if any(n in name_lower for n in frontend_names):
        return "frontend_app"
    if any(n in name_lower for n in infra_names):
        return "infra_devops"
    if any(n in name_lower for n in mobile_names):
        return "mobile_app"
    if any(n in name_lower for n in cli_names):
        return "cli_tool"
    if any(n in name_lower for n in data_names):
        return "data_science"
    if any(n in name_lower for n in shared_names):
        return "library_sdk"
    if any(n in name_lower for n in docs_names):
        return "generic"

    # --- Language / framework signals within this layer
    if any(fw in stack_all for fw in ("react", "vue", "angular", "svelte", "next")):
        if any(fw in all_paths or fw in all_langs for fw in ("tsx", "jsx", "vue", "svelte")):
            return "frontend_app"
    if any(fw in stack_all for fw in ("terraform", "helm", "ansible", "pulumi")):
        if any(ext in all_paths for ext in (".tf", "helm", "ansible", "k8s")):
            return "infra_devops"
    if any(fw in stack_all for fw in ("expo", "react native", "flutter", "swift", "kotlin")):
        return "mobile_app"

    # --- Path-based signals inside the layer
    if any(p in all_paths for p in ("controller", "handler", "route", "endpoint", "router")):
        return "web_service"
    if any(p in all_paths for p in ("component", "screen", "page", "widget")):
        if any(p in all_paths for p in ("store", "hook", "context", "redux")):
            return "frontend_app"
    if any(p in all_paths for p in ("train", "model", "pipeline", "dataset")):
        return "data_science"
    if any(p in all_paths for p in ("cmd", "command", "flag", "arg")):
        return "cli_tool"

    # --- Default for backend-named layers
    if any(n in name_lower for n in backend_names):
        return "web_service"

    # --- Fallback: use file count and content
    if num_files >= 5:
        return "web_service"   # most likely for a substantial unknown layer
    return "library_sdk"       # small layer = probably a shared lib


def _layer_repo_map(layer_name: str, layer_data: dict, repo_map: dict) -> dict:
    """
    Build a scoped repo_map for a single layer.
    Preserves global tech_stack and config_files (they apply to all layers).
    """
    return {
        "root":         repo_map.get("root", ""),
        "tech_stack":   repo_map.get("tech_stack", []),
        "entry_points": [
            ep for ep in repo_map.get("entry_points", [])
            if layer_data.get("path", layer_name) in ep
               or ep.startswith(layer_name)
        ],
        "config_files": repo_map.get("config_files", []),
        "layers":       {layer_name: layer_data},
        "stats": {
            "total_files": len(layer_data.get("modules", [])),
            "by_extension": {},
            "rg_available": repo_map.get("stats", {}).get("rg_available", False),
            "rg_version":   repo_map.get("stats", {}).get("rg_version", None),
        },
    }


def _monorepo_root_chapters(repo_map: dict, language: str,
                             project_name: str, layer_types: dict[str, str],
                             graph_context: str = "") -> list[dict]:
    """
    Build the root-level chapters for a monorepo.
    These describe the whole project and link to per-layer docs.
    """
    layer_summary = "\n".join(
        f"  - **{name}** ({ltype.replace('_', ' ')}): `{repo_map['layers'][name]['path']}`"
        for name, ltype in layer_types.items()
    )

    root_chapters_meta = [
        {"file": "index.md",           "title": "Home",        "description": "Monorepo overview and navigation"},
        {"file": "01-overview.md",     "title": "Overview",    "description": "All layers, tech stack, structure"},
        {"file": "02-quickstart.md",   "title": "Quick Start", "description": "How to run the full project"},
        {"file": "03-architecture.md", "title": "Architecture","description": "Layer interaction and data flow"},
        {"file": "06b-service-map.md", "title": "Service Map", "description": "Inter-service contracts and communication"},
        {"file": "07-dev-guide.md",    "title": "Dev Guide",   "description": "Monorepo conventions and workflows"},
    ]

    result = []
    for ch in root_chapters_meta:
        f = ch["file"]
        sys_ = _base_system(language)

        if f == "index.md":
            # Special monorepo index: links to all layer sub-docs
            layer_links = "\n".join(
                f"| [{name}]({name}/index) | {ltype.replace('_', ' ').title()} | `{repo_map['layers'][name]['path']}` |"
                for name, ltype in layer_types.items()
            )
            user = f"""Generate **index.md** — the home page for the monorepo **{project_name}**.

{_repo_context(repo_map, graph_context=graph_context)}

### Layers in this monorepo
{layer_summary}

## What this document must contain
1. `# {project_name}` heading with 2-3 sentence description
2. **Layer overview table**:
   | Layer | Type | Path |
   |-------|------|------|
{layer_links}
3. **Quick start** — single command to start all services (docker-compose, make, etc.)
4. **Documentation map** — links to root-level docs AND per-layer docs
5. **Repository structure** — annotated tree showing all layers

Language: {language}"""

        elif f == "01-overview.md":
            user = f"""Generate **01-overview.md** — the global overview for the monorepo **{project_name}**.

{_repo_context(repo_map, graph_context=graph_context)}

### Layers
{layer_summary}

## What this document must contain
1. `# Overview` heading
2. **Global tech stack table** — ALL technologies across all layers
3. **Layer breakdown** — for each layer: purpose, primary language, key responsibilities
4. **Shared dependencies** — packages/libraries used across multiple layers
5. **Repository structure** — full annotated directory tree
6. **Entry points** — how to start each layer independently

Language: {language}"""

        elif f == "02-quickstart.md":
            user = f"""Generate **02-quickstart.md** — the Quick Start for the full monorepo **{project_name}**.

{_repo_context(repo_map, graph_context=graph_context)}

### Layers to start
{layer_summary}

## What this document must contain
1. `# Quick Start` heading
2. **Prerequisites** — everything needed across all layers
3. **Full stack startup** — how to run all layers together (docker-compose, Makefile, scripts)
4. **Per-layer startup** — how to run each layer independently (for development)
5. **Verification** — how to confirm each layer is running
6. **Common setup issues** — top 3 problems when setting up the full stack

Language: {language}"""

        elif f == "03-architecture.md":
            user = f"""Generate **03-architecture.md** — the Architecture chapter for the monorepo **{project_name}**.

{_repo_context(repo_map, graph_context=graph_context)}

### Layers and their types
{layer_summary}

## What this document must contain
1. `# Architecture` heading
2. **System overview** — how all layers fit together
3. **Architecture diagram** — Mermaid diagram showing ALL layers and their relationships:
   ```mermaid
   graph LR
     LayerA --> LayerB
     LayerB --> Database
   ```
4. **Per-layer architecture** — brief description of each layer's internal design
5. **Communication patterns** — REST, gRPC, events, shared DB, etc. between layers
6. **Data flow** — end-to-end sequence diagram for the most important user flow
7. **Deployment overview** — how layers are deployed together

Language: {language}"""

        else:
            # Reuse existing dispatcher for service-map and dev-guide
            sys_, user = _dispatch_prompt(f, repo_map, language, project_name,
                                           "monorepo", root_chapters_meta,
                                           graph_context=graph_context)

        result.append({
            "file":         f,
            "title":        ch["title"],
            "description":  ch["description"],
            "project_type": "monorepo",
            "subdir":       None,   # root level
            "system":       sys_,
            "user":         user,
        })

    return result


def _layer_chapters(layer_name: str, layer_data: dict, layer_type: str,
                    repo_map: dict, language: str, project_name: str) -> list[dict]:
    """
    Build per-layer chapter list for a monorepo layer.
    Returns chapters with subdir=layer_name so they go into docs/{layer_name}/.
    """
    layer_rm = _layer_repo_map(layer_name, layer_data, repo_map)

    # Get type-specific chapters (not universal ones — those are at root level)
    type_chapters = ADAPTIVE_CHAPTERS.get(layer_type, ADAPTIVE_CHAPTERS["generic"])

    # Layer index page
    layer_index = {
        "file":  "index.md",
        "title": f"{layer_name.title()} Layer",
        "description": f"Overview of the {layer_name} layer",
    }

    all_layer_chapters = [layer_index] + type_chapters
    result = []

    for ch in all_layer_chapters:
        f = ch["file"]

        if f == "index.md":
            # Layer-specific index
            type_chapter_links = "\n".join(
                f"  - [{c['title']}]({c['file'].replace('.md', '')})"
                for c in type_chapters
            )
            sys_ = _base_system(language)
            user = f"""Generate **index.md** — the home page for the **{layer_name}** layer of {project_name}.

{_repo_context(layer_rm)}

## What this document must contain
1. `# {layer_name.title()} Layer` heading with 2-3 sentence description of this layer's role
2. **Layer type**: {layer_type.replace('_', ' ').title()}
3. **Tech stack** — technologies specific to this layer
4. **Key modules** — the most important files/modules in this layer
5. **Navigation** — links to the chapters in this layer:
{type_chapter_links}
6. **How it connects** — brief description of how this layer interacts with others

Language: {language}"""
        else:
            sys_, user = _dispatch_prompt(
                f, layer_rm, language,
                f"{project_name} / {layer_name.title()}",
                layer_type, all_layer_chapters
            )

        result.append({
            "file":         f,
            "title":        ch["title"],
            "description":  ch["description"],
            "project_type": layer_type,
            "subdir":       layer_name,
            "system":       sys_,
            "user":         user,
        })

    return result


def get_monorepo_chapter_prompts(repo_map: dict, language: str,
                                  project_name: str) -> list[dict]:
    """
    Build the full hierarchical chapter list for a monorepo.

    Returns a flat list where each entry has a "subdir" key:
      - subdir=None  → root docs/  (global overview, architecture, service map)
      - subdir="frontend" → docs/frontend/  (layer-specific chapters)
      - subdir="backend"  → docs/backend/
      - etc.

    docs_generator.py uses subdir to write to the right folder.
    """
    layers = repo_map.get("layers", {})

    # Classify each layer independently
    layer_types = {
        name: classify_layer(name, data, repo_map)
        for name, data in layers.items()
    }

    all_chapters = []

    # 1. Root-level chapters (monorepo global)
    root_chapters = _monorepo_root_chapters(repo_map, language, project_name, layer_types)
    all_chapters.extend(root_chapters)

    # 2. Per-layer chapters
    for layer_name, layer_data in layers.items():
        layer_type = layer_types[layer_name]
        layer_chs = _layer_chapters(
            layer_name, layer_data, layer_type,
            repo_map, language, project_name
        )
        all_chapters.extend(layer_chs)

    return all_chapters


# ---------------------------------------------------------------------------
# Update get_chapter_prompts to route monorepos through the new path
# ---------------------------------------------------------------------------

_original_get_chapter_prompts = get_chapter_prompts


def get_chapter_prompts(repo_map: dict, language: str, project_name: str,  # noqa: F811
                        graph_context: str = "",
                        short_graph_context: str = "") -> list[dict]:
    """
    Main entry point. Routes monorepos through hierarchical generation,
    single projects through the original adaptive path.

    Each returned entry has:
      file, title, description, project_type, system, user
    Monorepo entries also have:
      subdir  (None = root, "layername" = per-layer subfolder)

    Args:
        graph_context: Full dependency analysis for architecture chapters.
        short_graph_context: Short summary for other chapters.
    """
    # Allow repoforge.yaml to force the project type
    cfg_type = repo_map.get("repoforge_config", {}).get("project_type")
    project_type = cfg_type or classify_project(repo_map)

    if project_type == "monorepo":
        return get_monorepo_chapter_prompts(repo_map, language, project_name)

    # Single project: use original adaptive path, add subdir=None for compatibility
    chapters = _original_get_chapter_prompts(
        repo_map, language, project_name,
        graph_context=graph_context,
        short_graph_context=short_graph_context,
    )
    for ch in chapters:
        ch.setdefault("subdir", None)
    return chapters
