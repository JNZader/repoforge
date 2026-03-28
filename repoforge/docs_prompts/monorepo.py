"""Monorepo hierarchical documentation — root chapters and per-layer chapters."""

from __future__ import annotations

from .system import _base_system
from .context import _repo_context
from .classify import classify_layer, _layer_repo_map
from .chapters import (
    ADAPTIVE_CHAPTERS,
    _dispatch_prompt,
    get_chapter_prompts as _single_project_get_chapter_prompts,
)


# ===========================================================================
# MONOREPO HIERARCHICAL DOCUMENTATION
# ===========================================================================
#
# For monorepos, we generate a two-level structure:
#
#   docs/
#   |- index.md              <- monorepo home (links to all layers)
#   |- 01-overview.md        <- global tech stack, all layers
#   |- 02-quickstart.md      <- how to run the whole project
#   |- 03-architecture.md    <- how layers interact
#   |- 06b-service-map.md    <- inter-service contracts
#   |- 07-dev-guide.md       <- monorepo-level conventions
#   |- frontend/             <- per-layer docs (type = frontend_app)
#   |   |- index.md
#   |   |- 04-core-mechanisms.md
#   |   |- 05-components.md
#   |   |- 06-state.md
#   |- backend/              <- per-layer docs (type = web_service)
#   |   |- index.md
#   |   |- 04-core-mechanisms.md
#   |   |- 05-data-models.md
#   |   |- 06-api-reference.md
#   |- infra/                <- per-layer docs (type = infra_devops)
#       |- index.md
#       |- 04-resources.md
#       |- 05-variables.md
#       |- 06-deployment.md
#
# Each layer is classified independently by classify_layer().
# The output of get_chapter_prompts() for a monorepo is a flat list
# but each chapter has a "subdir" key (e.g. "frontend") which
# docs_generator.py uses to write to the correct subfolder.
# ===========================================================================


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
      - subdir=None  -> root docs/  (global overview, architecture, service map)
      - subdir="frontend" -> docs/frontend/  (layer-specific chapters)
      - subdir="backend"  -> docs/backend/
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
