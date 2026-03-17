"""
RepoForge - Agnostic code analysis tool that generates SKILL.md and AGENT.md
files ready for use in Claude Code and OpenCode.
"""

from .generator import generate_artifacts
from .server import serve_docs, serve_skills
from .docs_generator import generate_docs
from .exporter import export_llm_view

__version__ = "0.1.0"
__all__ = ["generate_artifacts", "generate_docs", "export_llm_view", "serve_docs", "serve_skills"]
