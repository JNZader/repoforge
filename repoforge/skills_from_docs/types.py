"""
types.py - Data models for skills-from-docs pipeline.

Defines the structured types used across ingest, extract, generate, and conflict modules.
"""

from dataclasses import dataclass, field
from enum import Enum


class SourceType(Enum):
    """Type of documentation source."""

    URL = "url"
    GITHUB_REPO = "github_repo"
    LOCAL_DIR = "local_dir"
    PDF = "pdf"
    YOUTUBE = "youtube"
    JUPYTER_NOTEBOOK = "jupyter_notebook"


@dataclass
class DocSection:
    """A section extracted from documentation."""

    heading: str
    level: int
    content: str


@dataclass
class CodeExample:
    """A code example extracted from documentation."""

    language: str
    code: str
    context: str  # heading it appeared under


@dataclass
class DocContent:
    """Structured content extracted from documentation sources."""

    title: str
    source: str
    sections: list[DocSection] = field(default_factory=list)
    code_examples: list[CodeExample] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)


@dataclass
class SkillConflict:
    """A detected conflict between generated and existing skill."""

    existing_skill: str
    generated_rule: str
    existing_rule: str
    description: str
