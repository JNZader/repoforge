"""
docs_prompts - Prompt templates for technical documentation generation.

This package was split from a single docs_prompts.py module.
All public symbols are re-exported here for backwards compatibility.
"""

from .builders import (
    architecture_prompt,
    index_prompt,
    overview_prompt,
    quickstart_prompt,
)
from .builders_extra import (
    api_reference_prompt,
    core_mechanisms_prompt,
    data_models_prompt,
    dev_guide_prompt,
)
from .chapters import (
    ADAPTIVE_CHAPTERS,
    UNIVERSAL_CHAPTERS,
    _adaptive_prompt,
    _dispatch_prompt,
)
from .chapters import (
    get_chapter_prompts as _original_get_chapter_prompts,
)
from .classify import _layer_repo_map, classify_layer, classify_project
from .context import (
    _build_directory_tree,
    _format_config_files,
    _format_entry_points,
    _format_layers,
    _format_modules,
    _format_stack,
    _repo_context,
    _repo_context_facts_only,
    _repo_context_light,
)
from .monorepo import (
    _layer_chapters,
    _monorepo_root_chapters,
    get_monorepo_chapter_prompts,
)
from .system import _base_system, _base_system_facts_only


def get_chapter_prompts(repo_map: dict, language: str, project_name: str,
                        graph_context: str = "",
                        short_graph_context: str = "",
                        doc_chunks: dict | None = None,
                        facts_only_context_by_chapter: dict[str, str] | None = None,
                        diagram_context: str = "",
                        dep_health_context: str = "",
                        coverage_context: str = "",
                        link_style: str = "backtick") -> list[dict]:
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
        doc_chunks: Pre-digested context chunks from doc_chunks.py.
        facts_only_context_by_chapter: Per-chapter facts-only context dict.
            Keys are chapter file names (e.g. "01-overview.md"); "_default" as
            fallback.  Non-architecture chapters use _base_system_facts_only and
            the matching context.  Architecture chapter is unchanged.
            None means no facts-only mode.
        diagram_context: Auto-generated Mermaid diagrams to embed in architecture chapter.
        dep_health_context: Dependency health analysis markdown to embed in dev guide.
        coverage_context: Unified coverage report markdown to embed in dev guide.
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
        doc_chunks=doc_chunks,
        facts_only_context_by_chapter=facts_only_context_by_chapter,
        diagram_context=diagram_context,
        dep_health_context=dep_health_context,
        coverage_context=coverage_context,
        link_style=link_style,
    )
    for ch in chapters:
        ch.setdefault("subdir", None)
    return chapters


__all__ = [
    "_base_system",
    "_base_system_facts_only",
    "_format_stack",
    "_format_layers",
    "_format_modules",
    "_build_directory_tree",
    "_format_entry_points",
    "_format_config_files",
    "_repo_context",
    "_repo_context_light",
    "_repo_context_facts_only",
    "index_prompt",
    "overview_prompt",
    "quickstart_prompt",
    "architecture_prompt",
    "core_mechanisms_prompt",
    "data_models_prompt",
    "api_reference_prompt",
    "dev_guide_prompt",
    "classify_project",
    "classify_layer",
    "_layer_repo_map",
    "UNIVERSAL_CHAPTERS",
    "ADAPTIVE_CHAPTERS",
    "_dispatch_prompt",
    "_adaptive_prompt",
    "_monorepo_root_chapters",
    "_layer_chapters",
    "get_monorepo_chapter_prompts",
    "get_chapter_prompts",
]
