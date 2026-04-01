"""Chapter prompt builders — core_mechanisms, data_models, api_reference, dev_guide."""

from __future__ import annotations

from .system import _base_system, _base_system_facts_only
from .context import (
    _repo_context,
    _repo_context_facts_only,
)


# ---------------------------------------------------------------------------
# Chapter 4: 04-core-mechanisms.md — Deep dive
# ---------------------------------------------------------------------------

def core_mechanisms_prompt(repo_map: dict, language: str, project_name: str,
                           graph_context: str = "",
                           doc_chunks: dict | None = None,
                           facts_only: bool = False) -> tuple[str, str]:
    # In facts-only mode, skip the per-module detail — facts carry this info
    if facts_only:
        modules_detail = ""
    else:
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

    # Focused context: endpoints, MCP tools, CLI commands
    chunks = doc_chunks or {}
    focused_parts = []
    for key in ("endpoints", "mcp_tools", "cli_commands"):
        chunk = chunks.get(key, "")
        if chunk:
            focused_parts.append(chunk)
    focused_section = "\n\n".join(focused_parts) if focused_parts else ""

    # Use ultra-light repo context in facts-only mode
    ctx_fn = _repo_context_facts_only if facts_only else _repo_context
    ctx = ctx_fn(repo_map, graph_context=graph_context)

    modules_block = ""
    if modules_detail:
        modules_block = f"""
### Most interesting modules (analyze these in depth)
{modules_detail}
"""

    user = f"""Generate **04-core-mechanisms.md** for **{project_name}**.

{ctx}
{modules_block}
{focused_section}
## Structure
`# Core Mechanisms` → identify 2-3 key workflows from entry points and facts.
Per mechanism: `## Name` with purpose, key files (actual paths), Mermaid flow diagram, code pattern (from real exports — no invented bodies), integration points.
End with cross-cutting concerns (error handling, logging, config).
Depth > breadth. Language: {language}
"""
    return _base_system(language), user


# ---------------------------------------------------------------------------
# Chapter 5: 05-data-models.md — Data structures
# ---------------------------------------------------------------------------

def data_models_prompt(repo_map: dict, language: str, project_name: str,
                       graph_context: str = "",
                       doc_chunks: dict | None = None,
                       facts_only: bool = False) -> tuple[str, str]:
    # In facts-only mode, skip the per-module scan — facts carry model info
    if facts_only:
        modules_text = ""
    else:
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

    # Focused context: pre-digested data models
    chunks = doc_chunks or {}
    models_chunk = chunks.get("data_models", "")
    focused_section = ""
    if models_chunk:
        focused_section = f"""
### Pre-digested Data Model Information (from AST — use these EXACT names and fields)
{models_chunk}

CRITICAL: Use ONLY the tables, types, and fields listed above. Do NOT invent fields or models
that are not in this extracted data.
"""

    # Use ultra-light repo context in facts-only mode
    ctx_fn = _repo_context_facts_only if facts_only else _repo_context
    ctx = ctx_fn(repo_map, graph_context=graph_context)

    modules_block = ""
    if modules_text:
        modules_block = f"""
### Modules likely containing data models/schemas
{modules_text}
"""

    user = f"""Generate **05-data-models.md** for **{project_name}**.

{ctx}
{modules_block}
{focused_section}
## Structure
`# Data Models` → overview of modeling approach (infer from imports).
Per model: `## ModelName` with purpose, fields table (Field|Type|Description), relationships.
Add Mermaid ER diagram if multiple models. Note validation patterns.
If no models detected, document key data structures. Mark inferred fields.
Language: {language}
"""
    return _base_system(language), user


# ---------------------------------------------------------------------------
# Chapter 6: 06-api-reference.md — Public API / endpoints
# ---------------------------------------------------------------------------

def api_reference_prompt(repo_map: dict, language: str, project_name: str,
                         graph_context: str = "",
                         doc_chunks: dict | None = None) -> tuple[str, str]:
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

    # Focused context: pre-digested endpoint data
    chunks = doc_chunks or {}
    endpoints_chunk = chunks.get("endpoints", "")
    focused_section = ""
    if endpoints_chunk:
        focused_section = f"""
### Pre-digested Endpoint Data (from source code analysis — use ONLY these endpoints)
{endpoints_chunk}

CRITICAL: Document ONLY the endpoints listed above. Do NOT invent endpoints, paths, or
handler names that are not in this extracted data. Format this data into proper API docs.
"""

    user = f"""Generate **06-api-reference.md** — the API Reference for **{project_name}**.

{_repo_context(repo_map, graph_context=graph_context)}

### Modules likely containing API endpoints/routes
{modules_text or "  (infer from modules with router/handler naming patterns)"}
{focused_section}
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
                     graph_context: str = "",
                     doc_chunks: dict | None = None,
                     facts_only: bool = False,
                     dep_health_context: str = "") -> tuple[str, str]:
    layers = repo_map.get("layers", {})

    # Use ultra-light repo context in facts-only mode
    ctx_fn = _repo_context_facts_only if facts_only else _repo_context
    ctx = ctx_fn(repo_map, graph_context=graph_context)

    layer_hint = "which layer to modify and how layers interact" if len(layers) > 1 else "file structure to follow"

    dep_health_section = ""
    if dep_health_context:
        dep_health_section = f"""
### Dependency Health Analysis (include this section in the output)
{dep_health_context}
"""

    user = f"""Generate **07-dev-guide.md** for **{project_name}**.

{ctx}
{dep_health_section}
## Structure
`# Developer Guide` → dev setup (hot reload, debug, test runner), project conventions (from actual names/paths), how to add a feature ({layer_hint}), testing (runner, patterns), common tasks table (dev server, tests, build, lint), code style tools.
{('Include a "## Dependency Health" section with the analysis data provided above.' if dep_health_context else '')}
Be specific to THIS project. Language: {language}
"""
    return _base_system(language), user
