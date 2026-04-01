"""Adaptive chapter catalog, dispatch, and prompt generation for project-type-specific chapters."""

from __future__ import annotations

from .system import _base_system, _base_system_facts_only
from .context import _repo_context
from .builders import (
    index_prompt,
    overview_prompt,
    quickstart_prompt,
    architecture_prompt,
)
from .builders_extra import (
    core_mechanisms_prompt,
    data_models_prompt,
    api_reference_prompt,
    dev_guide_prompt,
)
from .classify import classify_project
from .adaptive import _adaptive_prompt


# ===========================================================================
# PROJECT CLASSIFICATION + ADAPTIVE CHAPTERS
# ===========================================================================
#
# Instead of a fixed chapter set with optional slots, we classify the project
# type and build a tailored chapter list. Every project type gets chapters
# that make sense for IT specifically.
#
# Project types:
#   web_service    -> REST API / GraphQL / gRPC backend
#   cli_tool       -> Command-line application
#   library_sdk    -> Reusable library / SDK / package
#   data_science   -> ML / data pipeline / notebooks
#   frontend_app   -> SPA / web frontend (React, Vue, Angular, Svelte...)
#   mobile_app     -> iOS / Android / React Native / Flutter
#   desktop_app    -> Electron / Qt / native desktop
#   infra_devops   -> Terraform / Helm / Ansible / Docker Compose
#   monorepo       -> Multiple distinct apps in one repo (overrides others)
#   generic        -> Fallback -- uses the universal chapter set
# ===========================================================================


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
# Maps chapter file -> prompt function (new chapters + existing ones)
# ---------------------------------------------------------------------------

def _dispatch_prompt(chapter_file: str, repo_map: dict, language: str,
                     project_name: str, project_type: str,
                     active_chapters: list[dict],
                     graph_context: str = "",
                     doc_chunks: dict | None = None,
                     facts_only: bool = False,
                     diagram_context: str = "") -> tuple[str, str]:
    """Route a chapter file to its prompt function."""
    chunks = doc_chunks or {}

    # Existing prompts (reused across types)
    if chapter_file == "index.md":
        non_index = [c for c in active_chapters if c["file"] != "index.md"]
        return index_prompt(repo_map, language, project_name, non_index, graph_context=graph_context,
                            facts_only=facts_only)
    if chapter_file == "01-overview.md":
        return overview_prompt(repo_map, language, project_name, graph_context=graph_context,
                               doc_chunks=chunks)
    if chapter_file == "02-quickstart.md":
        return quickstart_prompt(repo_map, language, project_name, graph_context=graph_context,
                                  doc_chunks=chunks)
    if chapter_file == "03-architecture.md":
        return architecture_prompt(repo_map, language, project_name, graph_context=graph_context,
                                    doc_chunks=chunks, facts_only=facts_only,
                                    diagram_context=diagram_context)
    if chapter_file == "04-core-mechanisms.md":
        return core_mechanisms_prompt(repo_map, language, project_name, graph_context=graph_context,
                                       doc_chunks=chunks, facts_only=facts_only)
    if chapter_file == "05-data-models.md":
        return data_models_prompt(repo_map, language, project_name, graph_context=graph_context,
                                   doc_chunks=chunks, facts_only=facts_only)
    if chapter_file == "06-api-reference.md":
        return api_reference_prompt(repo_map, language, project_name, graph_context=graph_context,
                                     doc_chunks=chunks)
    if chapter_file == "07-dev-guide.md":
        return dev_guide_prompt(repo_map, language, project_name, graph_context=graph_context,
                                 doc_chunks=chunks, facts_only=facts_only)

    # Adaptive chapter prompts
    return _adaptive_prompt(chapter_file, repo_map, language, project_name, project_type,
                            graph_context=graph_context, doc_chunks=chunks)


# _adaptive_prompt moved to adaptive.py — imported at top of file


# ---------------------------------------------------------------------------
# Main entry point (single-project, non-monorepo)
# ---------------------------------------------------------------------------

def get_chapter_prompts(repo_map: dict, language: str, project_name: str,
                        graph_context: str = "",
                        short_graph_context: str = "",
                        doc_chunks: dict | None = None,
                        facts_only_context_by_chapter: dict[str, str] | None = None,
                        diagram_context: str = "") -> list[dict]:
    """
    Return the adaptive list of chapters to generate with their prompts.

    Detects project type first, then builds a tailored chapter list.
    Each entry: {"file": str, "title": str, "description": str, "system": str, "user": str}

    Args:
        graph_context: Full dependency analysis for architecture chapter.
        short_graph_context: Short summary for other chapters.
        doc_chunks: Pre-digested context chunks from doc_chunks.py.
            Keys: endpoints, data_models, mcp_tools, cli_commands, architecture, module_summaries.
        facts_only_context_by_chapter: Per-chapter facts-only context dict.
            Keys are chapter file names (e.g. "01-overview.md"); a "_default" key
            is used as fallback.  When provided, ALL chapters (including architecture
            and index) use per-chapter context and _base_system_facts_only.
            Architecture gets short graph + facts + API surface (no snippets/mermaid).
            Index gets minimal context (just facts).
            None means no facts-only mode (original behaviour).
    """
    project_type = classify_project(repo_map)
    chunks = doc_chunks or {}

    # Build chapter list: universal + type-specific
    type_chapters = ADAPTIVE_CHAPTERS.get(project_type, ADAPTIVE_CHAPTERS["generic"])

    # Build ordered chapter list:
    # index.md first, then 01-overview -> 03-architecture, then type-specific, then 07-dev-guide
    index_ch = [c for c in UNIVERSAL_CHAPTERS if c["file"] == "index.md"]
    pre_ch   = [c for c in UNIVERSAL_CHAPTERS
                if c["file"].startswith("0") and c["file"] <= "03-z"]
    post_ch  = [c for c in UNIVERSAL_CHAPTERS
                if c["file"].startswith("0") and c["file"] >= "07-"]
    all_chapters = index_ch + pre_ch + type_chapters + post_ch

    # Build prompts for each chapter
    result = []
    for chapter in all_chapters:
        is_architecture = chapter["file"] == "03-architecture.md"

        # When facts_only_context_by_chapter is provided, ALL chapters
        # (including architecture and index) use per-chapter context.
        # Architecture gets short graph + facts + API surface (no snippets).
        # Without facts_only, architecture gets full graph context.
        chapter_file = chapter["file"]
        if facts_only_context_by_chapter is not None:
            # Facts-only mode: ALL chapters use per-chapter context (including arch/index)
            ch_graph = facts_only_context_by_chapter.get(
                chapter_file,
                facts_only_context_by_chapter.get("_default", ""),
            )
            ch_system_override = _base_system_facts_only(language)
        elif is_architecture:
            # Normal mode: architecture gets full graph context
            ch_graph = graph_context
            ch_system_override = None
        else:
            # Normal mode: other chapters get short graph context
            ch_graph = short_graph_context
            ch_system_override = None

        is_facts_only = ch_system_override is not None

        system, user = _dispatch_prompt(
            chapter_file, repo_map, language, project_name,
            project_type, all_chapters, graph_context=ch_graph,
            doc_chunks=chunks, facts_only=is_facts_only,
            diagram_context=diagram_context if is_architecture else "",
        )

        # Override system prompt when using facts-only mode
        if ch_system_override is not None:
            system = ch_system_override

        result.append({
            "file":        chapter["file"],
            "title":       chapter["title"],
            "description": chapter["description"],
            "project_type": project_type,
            "system":      system,
            "user":        user,
        })

    return result
