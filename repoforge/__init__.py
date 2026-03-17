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
from .disclosure import (
    extract_tier,
    extract_frontmatter,
    build_discovery_index,
    estimate_tokens,
    has_tier_markers,
    count_tier_markers,
)
from .compressor import (
    SkillCompressor,
    CompressionResult,
    compress_file,
    compress_directory,
)
from .security import (
    SecurityScanner,
    ScanResult,
    Finding,
    Severity,
    scan_generated_output,
)
from .plugins import (
    Command,
    PluginManifest,
    build_commands,
    build_plugin_manifest,
    commands_prompt,
    manifest_to_json,
    manifest_to_markdown,
    write_plugin,
)
from .graph import (
    CodeGraph,
    Node,
    Edge,
    build_graph,
    build_graph_from_workspace,
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
    "extract_tier",
    "extract_frontmatter",
    "build_discovery_index",
    "estimate_tokens",
    "has_tier_markers",
    "count_tier_markers",
    "SkillCompressor",
    "CompressionResult",
    "compress_file",
    "compress_directory",
    "SecurityScanner",
    "ScanResult",
    "Finding",
    "Severity",
    "scan_generated_output",
    "Command",
    "PluginManifest",
    "build_commands",
    "build_plugin_manifest",
    "commands_prompt",
    "manifest_to_json",
    "manifest_to_markdown",
    "write_plugin",
    "CodeGraph",
    "Node",
    "Edge",
    "build_graph",
    "build_graph_from_workspace",
]
