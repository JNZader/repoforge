"""
RepoForge - Agnostic code analysis tool that generates SKILL.md and AGENT.md
files ready for use in Claude Code, OpenCode, Cursor, Codex, Gemini CLI, and
GitHub Copilot.
"""

from .generator import generate_artifacts
from .server import serve_docs, serve_skills
from .docs_generator import generate_docs
from .exporter import export_llm_view
from .scorer import SkillScorer, SkillScore
from .adapters import (
    adapt_for_cursor,
    adapt_for_codex,
    adapt_for_gemini,
    adapt_for_copilot,
    resolve_targets,
    ALL_TARGETS,
)

__version__ = "0.1.0"
__all__ = [
    "generate_artifacts",
    "generate_docs",
    "export_llm_view",
    "serve_docs",
    "serve_skills",
    "SkillScorer",
    "SkillScore",
    "adapt_for_cursor",
    "adapt_for_codex",
    "adapt_for_gemini",
    "adapt_for_copilot",
    "resolve_targets",
    "ALL_TARGETS",
]
