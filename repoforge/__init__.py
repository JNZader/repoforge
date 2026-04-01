"""
RepoForge - Agnostic code analysis tool that generates SKILL.md and AGENT.md
files ready for use in Claude Code, OpenCode, Cursor, Codex, Gemini CLI, and
GitHub Copilot.
"""

from .adapters import (
    ALL_TARGETS,
    adapt_for_codex,
    adapt_for_copilot,
    adapt_for_cursor,
    adapt_for_gemini,
    resolve_targets,
)
from .compressor import (
    CompressionResult,
    SkillCompressor,
    compress_directory,
    compress_file,
)
from .diagrams import (
    generate_all_diagrams,
    generate_call_flow_diagram,
    generate_dependency_diagram,
    generate_directory_diagram,
)
from .disclosure import (
    build_discovery_index,
    count_tier_markers,
    estimate_tokens,
    extract_frontmatter,
    extract_tier,
    has_tier_markers,
)
from .docs_generator import generate_docs
from .exporter import export_llm_view
from .generator import generate_artifacts
from .graph import (
    BlastRadiusResult,
    CodeGraph,
    Edge,
    Node,
    build_graph,
    build_graph_from_workspace,
    build_graph_v2,
    get_blast_radius_v2,
    is_test_file,
)
from .incremental import (
    ChapterEntry,
    Manifest,
    build_chapter_deps,
    get_changed_files,
    get_stale_chapters,
    load_manifest,
    save_manifest,
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
from .scorer import SkillScore, SkillScorer
from .dep_health import (
    DependencyHealthReport,
    DuplicateDep,
    LicenseConflict,
    OutdatedDep,
    analyze_dependency_health,
)
from .security import (
    Finding,
    ScanResult,
    SecurityScanner,
    Severity,
    scan_generated_output,
)
from .coverage import (
    CoverageFile,
    CoverageReport,
    auto_detect_and_parse,
    detect_coverage_files,
    parse_cobertura,
    parse_coverage_py_json,
    parse_jacoco,
    parse_lcov,
    render_coverage_markdown,
)
from .import_docs import (
    fetch_github_docs,
    fetch_npm_readme,
    fetch_pypi_description,
    import_docs,
)
from .server import serve_docs, serve_skills
from .watch import FileWatcher, WatchEvent, watch_docs

__version__ = "0.4.0"
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
    "DependencyHealthReport",
    "DuplicateDep",
    "LicenseConflict",
    "OutdatedDep",
    "analyze_dependency_health",
    "Command",
    "PluginManifest",
    "build_commands",
    "build_plugin_manifest",
    "commands_prompt",
    "manifest_to_json",
    "manifest_to_markdown",
    "write_plugin",
    "generate_dependency_diagram",
    "generate_directory_diagram",
    "generate_call_flow_diagram",
    "generate_all_diagrams",
    "Manifest",
    "ChapterEntry",
    "load_manifest",
    "save_manifest",
    "get_changed_files",
    "build_chapter_deps",
    "get_stale_chapters",
    "BlastRadiusResult",
    "CodeGraph",
    "Node",
    "Edge",
    "build_graph",
    "build_graph_from_workspace",
    "build_graph_v2",
    "get_blast_radius_v2",
    "is_test_file",
    "CoverageFile",
    "CoverageReport",
    "auto_detect_and_parse",
    "detect_coverage_files",
    "parse_cobertura",
    "parse_coverage_py_json",
    "parse_jacoco",
    "parse_lcov",
    "render_coverage_markdown",
    "FileWatcher",
    "WatchEvent",
    "watch_docs",
    "import_docs",
    "fetch_npm_readme",
    "fetch_pypi_description",
    "fetch_github_docs",
]
