"""Advanced documentation generators — changelog, API reference, onboarding.

These are deterministic (no LLM) generators that produce structured
markdown from git history, extracted facts, and repo metadata.

Usage:
    from repoforge.generators import generate_changelog, generate_api_reference
    changelog = generate_changelog(repo_root, max_commits=50)
    api_ref = generate_api_reference(facts=facts, ast_symbols=symbols)
"""

from __future__ import annotations

import logging
import re
import subprocess
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Changelog from git history
# ---------------------------------------------------------------------------


def generate_changelog(
    repo_root: Path,
    max_commits: int = 50,
) -> str:
    """Generate a Keep-a-Changelog-style changelog from git history.

    Groups commits by conventional commit type (feat, fix, refactor, etc.).
    Returns empty string if not a git repo.
    """
    repo_root = Path(repo_root)

    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={max_commits}", "--pretty=format:%s|||%an|||%as"],
            cwd=repo_root, capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""

    # Parse and group by type
    groups: dict[str, list[dict]] = defaultdict(list)
    for line in result.stdout.strip().splitlines():
        parts = line.split("|||")
        if len(parts) < 3:
            continue
        message, author, date = parts[0].strip(), parts[1].strip(), parts[2].strip()

        commit_type = _parse_commit_type(message)
        # Strip type prefix for cleaner display
        clean_msg = re.sub(r"^(feat|fix|refactor|docs|test|chore|ci|style|perf|build)(\(.*?\))?:\s*", "", message)
        groups[commit_type].append({"message": clean_msg, "author": author, "date": date})

    if not groups:
        return ""

    # Format as Keep-a-Changelog
    lines = ["# Changelog\n"]

    type_labels = {
        "feat": "Added",
        "fix": "Fixed",
        "refactor": "Changed",
        "docs": "Documentation",
        "test": "Tests",
        "chore": "Maintenance",
        "perf": "Performance",
        "other": "Other",
    }

    for commit_type in ["feat", "fix", "refactor", "perf", "docs", "test", "chore", "other"]:
        if commit_type not in groups:
            continue
        label = type_labels.get(commit_type, commit_type.title())
        lines.append(f"## {label}\n")
        for entry in groups[commit_type]:
            lines.append(f"- {entry['message']}")
        lines.append("")

    return "\n".join(lines).strip()


def _parse_commit_type(message: str) -> str:
    """Extract conventional commit type from message."""
    m = re.match(r"^(feat|fix|refactor|docs|test|chore|ci|style|perf|build)(\(.*?\))?:", message)
    if m:
        return m.group(1)
    return "other"


# ---------------------------------------------------------------------------
# API Reference from facts + AST symbols
# ---------------------------------------------------------------------------


def generate_api_reference(
    facts: list,
    ast_symbols: dict | None = None,
) -> str:
    """Generate deterministic API reference from extracted facts and AST symbols.

    No LLM required — formats endpoints, handlers, and models directly.
    """
    ast_symbols = ast_symbols or {}
    endpoints = [f for f in facts if f.fact_type == "endpoint"]
    ports = [f for f in facts if f.fact_type == "port"]

    if not endpoints and not ast_symbols:
        return ""

    lines = ["# API Reference\n"]

    # Server info
    if ports:
        lines.append(f"**Server port**: {ports[0].value}\n")

    # Endpoints table
    if endpoints:
        lines.append("## Endpoints\n")
        lines.append("| Method & Path | Handler | Location |")
        lines.append("|---------------|---------|----------|")

        for ep in endpoints:
            handler = _find_handler(ep, ast_symbols)
            handler_str = f"`{handler.name}()`" if handler else "—"
            lines.append(f"| `{ep.value}` | {handler_str} | {ep.file}:{ep.line} |")
        lines.append("")

    # Handler details
    handler_symbols = []
    for file_syms in ast_symbols.values():
        for sym in file_syms:
            if sym.kind == "function" and sym.return_type:
                handler_symbols.append(sym)

    if handler_symbols:
        lines.append("## Handlers\n")
        for sym in handler_symbols:
            lines.append(f"### `{sym.signature}`\n")
            if sym.params:
                lines.append("**Parameters**:")
                for p in sym.params:
                    lines.append(f"- `{p}`")
            if sym.return_type:
                lines.append(f"\n**Returns**: `{sym.return_type}`")
            lines.append(f"\n*{sym.file}:{sym.line}*\n")

    # Data models
    model_symbols = []
    for file_syms in ast_symbols.values():
        for sym in file_syms:
            if sym.kind in ("class", "struct", "schema") and sym.fields:
                model_symbols.append(sym)

    if model_symbols:
        lines.append("## Models\n")
        for sym in model_symbols:
            lines.append(f"### `{sym.name}`\n")
            lines.append(f"*{sym.file}:{sym.line}*\n")
            if sym.fields:
                lines.append("| Field | Type |")
                lines.append("|-------|------|")
                for field_str in sym.fields:
                    parts = field_str.split(":", 1) if ":" in field_str else field_str.split(" ", 1)
                    name = parts[0].strip()
                    ftype = parts[1].strip() if len(parts) > 1 else "—"
                    lines.append(f"| `{name}` | `{ftype}` |")
            lines.append("")

    return "\n".join(lines).strip()


def _find_handler(endpoint_fact, ast_symbols: dict):
    """Try to find the handler function for an endpoint."""
    file_syms = ast_symbols.get(endpoint_fact.file, [])
    for sym in file_syms:
        if sym.kind == "function" and abs(sym.line - endpoint_fact.line) <= 15:
            return sym
    return None


# ---------------------------------------------------------------------------
# Onboarding guide from repo metadata
# ---------------------------------------------------------------------------


def generate_onboarding(
    repo_map: dict,
    project_name: str,
) -> str:
    """Generate a getting-started onboarding guide from repo metadata.

    No LLM — uses repo map structure to create deterministic guide.
    """
    tech_stack = repo_map.get("tech_stack", [])
    entry_points = repo_map.get("entry_points", [])
    config_files = repo_map.get("config_files", [])
    layers = repo_map.get("layers", {})

    lines = [f"# Getting Started with {project_name}\n"]

    # Tech stack
    if tech_stack:
        lines.append("## Tech Stack\n")
        for tech in tech_stack:
            lines.append(f"- {tech}")
        lines.append("")

    # Prerequisites
    lines.append("## Prerequisites\n")
    prereqs = _infer_prerequisites(tech_stack, config_files)
    for prereq in prereqs:
        lines.append(f"- {prereq}")
    lines.append("")

    # Setup
    lines.append("## Quick Setup\n")
    setup_steps = _infer_setup_steps(tech_stack, config_files)
    for i, step in enumerate(setup_steps, 1):
        lines.append(f"{i}. {step}")
    lines.append("")

    # Entry points
    if entry_points:
        lines.append("## Entry Points\n")
        lines.append("Start here when reading the code:\n")
        for ep in entry_points:
            lines.append(f"- `{ep}`")
        lines.append("")

    # Project structure
    if layers:
        lines.append("## Project Structure\n")
        for layer_name, layer_data in layers.items():
            modules = layer_data.get("modules", [])
            lines.append(f"### {layer_name}/ ({len(modules)} modules)\n")
            for mod in modules[:10]:
                desc = mod.get("summary_hint", "")
                if desc:
                    lines.append(f"- `{mod['path']}` — {desc}")
                else:
                    lines.append(f"- `{mod['path']}`")
            if len(modules) > 10:
                lines.append(f"- ... and {len(modules) - 10} more")
            lines.append("")

    return "\n".join(lines).strip()


def _infer_prerequisites(tech_stack: list[str], config_files: list[str]) -> list[str]:
    """Infer prerequisites from tech stack."""
    prereqs = []
    stack_lower = " ".join(tech_stack).lower()

    if "python" in stack_lower:
        prereqs.append("Python 3.10+")
    if "node" in stack_lower or "typescript" in stack_lower or "javascript" in stack_lower:
        prereqs.append("Node.js 18+")
    if "go" in stack_lower:
        prereqs.append("Go 1.21+")
    if "rust" in stack_lower:
        prereqs.append("Rust (latest stable)")
    if "java" in stack_lower:
        prereqs.append("JDK 17+")
    if "docker" in stack_lower or any("docker" in f.lower() for f in config_files):
        prereqs.append("Docker")

    if not prereqs:
        prereqs.append("See project documentation for requirements")

    return prereqs


def _infer_setup_steps(tech_stack: list[str], config_files: list[str]) -> list[str]:
    """Infer setup steps from tech stack and config files."""
    steps = ["Clone the repository"]
    stack_lower = " ".join(tech_stack).lower()
    config_names = [f.lower() for f in config_files]

    if "pyproject.toml" in config_names or "requirements.txt" in config_names:
        steps.append("Install dependencies: `pip install -e .` or `uv sync`")
    elif "package.json" in config_names:
        steps.append("Install dependencies: `npm install`")
    elif "go.mod" in config_names:
        steps.append("Install dependencies: `go mod download`")
    elif "cargo.toml" in config_names:
        steps.append("Build: `cargo build`")

    if any("docker" in f for f in config_names):
        steps.append("Or use Docker: `docker compose up`")

    steps.append("Run the project (see Entry Points above)")
    return steps
