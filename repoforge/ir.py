"""Intermediate Representation types for the documentation pipeline.

These dataclasses define the contracts between pipeline stages,
replacing the untyped dicts that were previously passed around.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChapterSpec:
    """A chapter to be generated — metadata + prompts."""

    file: str                           # "01-overview.md"
    title: str                          # "Overview"
    description: str
    project_type: str
    system_prompt: str
    user_prompt: str
    subdir: Optional[str] = None        # for monorepos: "frontend", "backend"


@dataclass
class GeneratedChapter:
    """A chapter after LLM generation + optional post-processing."""

    spec: ChapterSpec
    raw_content: str
    final_content: str
    corrections: list = field(default_factory=list)
    verification_issues: list = field(default_factory=list)


@dataclass
class DocumentationResult:
    """Final output of the documentation pipeline."""

    project_name: str
    language: str
    output_dir: str
    chapters: list[GeneratedChapter] = field(default_factory=list)
    docsify_files: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
