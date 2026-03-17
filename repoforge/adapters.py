"""
adapters.py - Format adapters for different AI coding tools.

Converts already-generated SKILL.md / AGENT.md content into formats
compatible with Cursor, Codex/OpenAI, Gemini CLI, and GitHub Copilot.

All functions are PURE — they take content in and return content out.
No LLM calls, no filesystem access, no side effects.

Supported targets:
  - cursor   → .cursor/rules/<name>.mdc (MDC = Markdown with Context)
  - codex    → AGENTS.md (single file, all skills + agents combined)
  - gemini   → GEMINI.md (single file, all instructions)
  - copilot  → .github/copilot-instructions.md (single file)
"""

from __future__ import annotations

import re
from datetime import date


# All valid target identifiers (order = display order)
ALL_TARGETS = ("claude", "opencode", "cursor", "codex", "gemini", "copilot")

# Targets that are handled by adapters (not the legacy mirror/default flow)
ADAPTER_TARGETS = ("cursor", "codex", "gemini", "copilot")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_yaml_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """
    Extract YAML frontmatter fields and the body from a SKILL.md / AGENT.md.

    Returns (frontmatter_dict, body_without_frontmatter).
    Frontmatter dict has string values only — enough for name/description.
    """
    fm: dict[str, str] = {}
    body = content

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if match:
        raw = match.group(1)
        body = content[match.end():]

        # Simple line-based YAML parsing (no pyyaml dep for pure functions)
        for line in raw.splitlines():
            if ":" in line and not line.startswith(" "):
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if val:
                    fm[key] = val
            elif line.startswith("  ") and fm:
                # Continuation of previous value (e.g. multi-line description)
                last_key = list(fm.keys())[-1]
                fm[last_key] += " " + line.strip()

    return fm, body


def _layer_to_globs(layer_name: str, tech_stack: list[str] | None = None) -> list[str]:
    """
    Map a layer name to reasonable glob patterns for Cursor rules.

    Uses tech stack hints to pick the right extensions.
    """
    py_exts = ["**/*.py"]
    ts_exts = ["**/*.ts", "**/*.tsx"]
    js_exts = ["**/*.js", "**/*.jsx"]
    go_exts = ["**/*.go"]
    rs_exts = ["**/*.rs"]
    java_exts = ["**/*.java"]

    stack = set(tech_stack or [])

    # Determine extensions based on tech stack
    if stack & {"Python", "FastAPI", "Django", "Flask"}:
        exts = py_exts
    elif stack & {"TypeScript", "React", "Next.js", "Vue", "Svelte"}:
        exts = ts_exts + js_exts
    elif stack & {"Node.js", "Express", "Fastify"}:
        exts = js_exts + ts_exts
    elif stack & {"Go"}:
        exts = go_exts
    elif stack & {"Rust"}:
        exts = rs_exts
    elif stack & {"Java"}:
        exts = java_exts
    else:
        # Fallback: common source extensions
        exts = py_exts + ts_exts + js_exts

    # Prefix with layer path if not "main" or "."
    if layer_name in ("main", "."):
        return exts

    return [f"{layer_name}/{e}" for e in exts]


def _build_toc(sections: list[tuple[str, str]]) -> str:
    """Build a markdown table of contents from (title, anchor) pairs."""
    lines = ["## Table of Contents\n"]
    for title, anchor in sections:
        lines.append(f"- [{title}](#{anchor})")
    return "\n".join(lines) + "\n"


def _skill_name_from_path(rel_path: str) -> str:
    """
    Derive a human-readable skill name from a relative path.

    Examples:
        "backend/SKILL.md"         → "backend"
        "backend/users/SKILL.md"   → "backend-users"
        "frontend/SKILL.md"        → "frontend"
    """
    parts = rel_path.replace("\\", "/").split("/")
    # Remove SKILL.md / AGENT.md from the end
    parts = [p for p in parts if p not in ("SKILL.md", "AGENT.md", "skills", "agents")]
    return "-".join(parts) if parts else "main"


def _make_anchor(text: str) -> str:
    """Convert a title to a markdown anchor."""
    return re.sub(r"[^a-z0-9-]", "", text.lower().replace(" ", "-"))


# ---------------------------------------------------------------------------
# Cursor adapter
# ---------------------------------------------------------------------------

def adapt_for_cursor(
    skills: dict[str, str],
    repo_map: dict | None = None,
) -> dict[str, str]:
    """
    Convert SKILL.md content to Cursor .mdc format.

    Args:
        skills: dict of {relative_path: content}
                e.g. {"backend/SKILL.md": "---\\nname: backend-layer\\n..."}
        repo_map: the repo analysis map (used for tech stack → glob hints)

    Returns:
        dict of {output_path: content} for Cursor format.
        e.g. {".cursor/rules/backend-layer.mdc": "---\\ndescription: ...\\n---\\n..."}
    """
    tech_stack = repo_map.get("tech_stack", []) if repo_map else []
    result: dict[str, str] = {}

    for rel_path, content in skills.items():
        fm, body = _strip_yaml_frontmatter(content)

        # Derive name and description from frontmatter
        name = fm.get("name", _skill_name_from_path(rel_path))
        description = fm.get("description", f"Patterns for {name}")

        # Determine layer from path for glob generation
        parts = rel_path.replace("\\", "/").split("/")
        layer = parts[0] if parts else "main"

        globs = _layer_to_globs(layer, tech_stack)

        # Build MDC frontmatter
        globs_str = ", ".join(f'"{g}"' for g in globs)
        mdc_lines = [
            "---",
            f"description: {description}",
            f"globs: [{globs_str}]",
            "alwaysApply: false",
            "---",
            "",
        ]

        # Append the body (skill content without original frontmatter)
        mdc_content = "\n".join(mdc_lines) + body

        out_path = f".cursor/rules/{name}.mdc"
        result[out_path] = mdc_content

    return result


# ---------------------------------------------------------------------------
# Codex / OpenAI adapter
# ---------------------------------------------------------------------------

def adapt_for_codex(
    skills: dict[str, str],
    agents: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Combine all skills and agents into a single AGENTS.md for Codex/OpenAI.

    Args:
        skills: dict of {relative_path: content}
        agents: dict of {relative_path: content} (optional)

    Returns:
        {"AGENTS.md": combined_content}
    """
    sections: list[tuple[str, str]] = []  # (title, anchor) for TOC
    parts: list[str] = []

    # Header
    parts.append("# Project Instructions (AGENTS.md)\n")
    parts.append(f"> Auto-generated by RepoForge on {date.today().isoformat()}\n")
    parts.append("> This file provides project-specific instructions for Codex / OpenAI agents.\n")

    # Collect sections for TOC
    skill_items: list[tuple[str, str, str]] = []  # (name, anchor, body)
    for rel_path, content in skills.items():
        fm, body = _strip_yaml_frontmatter(content)
        name = fm.get("name", _skill_name_from_path(rel_path))
        title = f"Skill: {name}"
        anchor = _make_anchor(title)
        skill_items.append((title, anchor, body))
        sections.append((title, anchor))

    agent_items: list[tuple[str, str, str]] = []
    if agents:
        for rel_path, content in agents.items():
            fm, body = _strip_yaml_frontmatter(content)
            name = fm.get("name", _skill_name_from_path(rel_path))
            title = f"Agent: {name}"
            anchor = _make_anchor(title)
            agent_items.append((title, anchor, body))
            sections.append((title, anchor))

    # Build TOC
    if sections:
        parts.append(_build_toc(sections))

    # Skills section
    if skill_items:
        parts.append("\n---\n")
        parts.append("## Skills\n")
        for title, _anchor, body in skill_items:
            parts.append(f"### {title}\n")
            parts.append(body.strip())
            parts.append("\n")

    # Agents section
    if agent_items:
        parts.append("\n---\n")
        parts.append("## Agents\n")
        for title, _anchor, body in agent_items:
            parts.append(f"### {title}\n")
            parts.append(body.strip())
            parts.append("\n")

    return {"AGENTS.md": "\n".join(parts) + "\n"}


# ---------------------------------------------------------------------------
# Gemini CLI adapter
# ---------------------------------------------------------------------------

def adapt_for_gemini(
    skills: dict[str, str],
    agents: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Combine all skills and agents into a single GEMINI.md for Gemini CLI.

    Args:
        skills: dict of {relative_path: content}
        agents: dict of {relative_path: content} (optional)

    Returns:
        {"GEMINI.md": combined_content}
    """
    sections: list[tuple[str, str]] = []
    parts: list[str] = []

    # Gemini-specific header
    parts.append("# Project Instructions (GEMINI.md)\n")
    parts.append(f"> Auto-generated by RepoForge on {date.today().isoformat()}\n")
    parts.append("> These instructions are loaded by Gemini CLI for project context.\n")

    # Collect items
    skill_items: list[tuple[str, str, str]] = []
    for rel_path, content in skills.items():
        fm, body = _strip_yaml_frontmatter(content)
        name = fm.get("name", _skill_name_from_path(rel_path))
        title = f"Skill: {name}"
        anchor = _make_anchor(title)
        skill_items.append((title, anchor, body))
        sections.append((title, anchor))

    agent_items: list[tuple[str, str, str]] = []
    if agents:
        for rel_path, content in agents.items():
            fm, body = _strip_yaml_frontmatter(content)
            name = fm.get("name", _skill_name_from_path(rel_path))
            title = f"Agent: {name}"
            anchor = _make_anchor(title)
            agent_items.append((title, anchor, body))
            sections.append((title, anchor))

    # TOC
    if sections:
        parts.append(_build_toc(sections))

    # Skills
    if skill_items:
        parts.append("\n---\n")
        parts.append("## Skills\n")
        for title, _anchor, body in skill_items:
            parts.append(f"### {title}\n")
            parts.append(body.strip())
            parts.append("\n")

    # Agents
    if agent_items:
        parts.append("\n---\n")
        parts.append("## Agents\n")
        for title, _anchor, body in agent_items:
            parts.append(f"### {title}\n")
            parts.append(body.strip())
            parts.append("\n")

    return {"GEMINI.md": "\n".join(parts) + "\n"}


# ---------------------------------------------------------------------------
# GitHub Copilot adapter
# ---------------------------------------------------------------------------

def adapt_for_copilot(
    skills: dict[str, str],
) -> dict[str, str]:
    """
    Combine all skills into .github/copilot-instructions.md for GitHub Copilot.

    Args:
        skills: dict of {relative_path: content}

    Returns:
        {".github/copilot-instructions.md": combined_content}
    """
    parts: list[str] = []

    parts.append("# Copilot Instructions\n")
    parts.append(f"> Auto-generated by RepoForge on {date.today().isoformat()}\n")

    for rel_path, content in skills.items():
        fm, body = _strip_yaml_frontmatter(content)
        name = fm.get("name", _skill_name_from_path(rel_path))
        parts.append(f"\n## {name}\n")
        parts.append(body.strip())
        parts.append("\n")

    return {".github/copilot-instructions.md": "\n".join(parts) + "\n"}


# ---------------------------------------------------------------------------
# Dispatcher — run adapters for requested targets
# ---------------------------------------------------------------------------

def resolve_targets(targets_str: str) -> list[str]:
    """
    Parse a comma-separated targets string into a validated list.

    Supports:
        "all"                         → all 6 targets
        "claude,cursor"               → ["claude", "cursor"]
        "claude,opencode"             → ["claude", "opencode"] (default)

    Raises ValueError for unknown target names.
    """
    raw = [t.strip().lower() for t in targets_str.split(",") if t.strip()]

    if "all" in raw:
        return list(ALL_TARGETS)

    unknown = [t for t in raw if t not in ALL_TARGETS]
    if unknown:
        raise ValueError(
            f"Unknown target(s): {', '.join(unknown)}. "
            f"Valid targets: {', '.join(ALL_TARGETS)}, all"
        )

    # Dedupe, preserve order
    return list(dict.fromkeys(raw))


def run_adapters(
    targets: list[str],
    skills: dict[str, str],
    agents: dict[str, str] | None = None,
    repo_map: dict | None = None,
) -> dict[str, str]:
    """
    Run the appropriate adapters for the requested targets.

    Args:
        targets: list of target names (e.g. ["cursor", "codex"])
        skills: dict of {relative_path: content} for skills
        agents: dict of {relative_path: content} for agents (optional)
        repo_map: the repo analysis map (optional, used by cursor)

    Returns:
        dict of {output_path: content} for all adapter outputs combined.
        Does NOT include claude/opencode outputs (handled by generator.py).
    """
    result: dict[str, str] = {}

    if "cursor" in targets:
        result.update(adapt_for_cursor(skills, repo_map))

    if "codex" in targets:
        result.update(adapt_for_codex(skills, agents))

    if "gemini" in targets:
        result.update(adapt_for_gemini(skills, agents))

    if "copilot" in targets:
        result.update(adapt_for_copilot(skills))

    return result
