"""Intermediate Representation package for the repoforge pipeline.

Re-exports all IR types so existing imports continue to work:

    from repoforge.ir import ChapterSpec, GeneratedChapter, DocumentationResult
"""

# Pipeline stage types (moved from ir.py)
# Context bundle
from repoforge.ir.context import ContextBundle

# Extraction stubs
from repoforge.ir.extraction import APIEndpoint, DependencyEdge, SymbolRef
from repoforge.ir.pipeline import (
    ChapterSpec,
    DocumentationResult,
    GeneratedChapter,
)

# Scanner / repo-map types
from repoforge.ir.repo import (
    BuildMetadata,
    LayerInfo,
    ModuleInfo,
    RepoMap,
    TechStack,
)

__all__ = [
    # pipeline
    "ChapterSpec",
    "GeneratedChapter",
    "DocumentationResult",
    # repo
    "RepoMap",
    "LayerInfo",
    "ModuleInfo",
    "TechStack",
    "BuildMetadata",
    # context
    "ContextBundle",
    # extraction
    "APIEndpoint",
    "DependencyEdge",
    "SymbolRef",
]
