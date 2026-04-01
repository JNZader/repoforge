"""
skills_from_docs - Generate SKILL.md files from documentation sources.

Supports URLs, GitHub repos, and local doc directories.
No LLM required — deterministic extraction and generation.

Usage:
    from repoforge.skills_from_docs import ingest, extract_content, generate_skill_md, check_conflicts

    raw_texts = ingest("https://docs.example.com/guide")
    doc = extract_content(raw_texts, source="https://docs.example.com/guide")
    skill_md = generate_skill_md(doc, name="example-lib")
    conflicts = check_conflicts(skill_md, existing_dir=".claude/skills")
"""

from .conflict import check_conflicts
from .extract import extract_content
from .generate import generate_skill_md
from .ingest import ingest

__all__ = [
    "ingest",
    "extract_content",
    "generate_skill_md",
    "check_conflicts",
]
