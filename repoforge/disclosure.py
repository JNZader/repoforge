"""
disclosure.py - Progressive disclosure utilities for tiered skill loading.

Skills can be structured with tier markers so AI agents don't waste context
tokens loading full skills they might not need:

  Level 1 (L1): Name + description + trigger only (~50-100 tokens) — discovery
  Level 2 (L2): + Quick Reference table + Critical Patterns summary (~300-500 tokens)
  Level 3 (L3): Full skill with all examples, anti-patterns, commands (~1500-3000 tokens)

Tier markers are HTML comments — invisible in rendered markdown:
  <!-- L1:START --> ... <!-- L1:END -->
  <!-- L2:START --> ... <!-- L2:END -->
  <!-- L3:START --> ... <!-- L3:END -->

All functions work WITHOUT LLM calls — pure string processing.
Backward compatible: skills without markers return full content.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier markers
# ---------------------------------------------------------------------------

_TIER_MARKERS = {
    1: ("<!-- L1:START -->", "<!-- L1:END -->"),
    2: ("<!-- L2:START -->", "<!-- L2:END -->"),
    3: ("<!-- L3:START -->", "<!-- L3:END -->"),
}


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def extract_tier(content: str, level: int = 3) -> str:
    """Extract content up to the specified tier level.

    Level 1: Only L1 block (discovery — name, description, trigger)
    Level 2: L1 + L2 blocks (quick reference + critical patterns summary)
    Level 3: Full content (L1 + L2 + L3 — all examples, anti-patterns, commands)

    If no tier markers found, returns full content (backward compatible).

    Args:
        content: Raw SKILL.md content string.
        level: 1, 2, or 3 (default 3 = full content).

    Returns:
        Content for the requested tier level, with frontmatter preserved.
    """
    if level not in (1, 2, 3):
        raise ValueError(f"level must be 1, 2, or 3 — got {level}")

    # Check if ANY tier markers exist
    has_markers = any(
        start in content
        for start, _ in _TIER_MARKERS.values()
    )

    if not has_markers:
        return content  # backward compatible

    # Extract frontmatter (always included in all tiers)
    frontmatter = ""
    body = content
    fm_match = re.match(r"^(---\s*\n.*?\n---\s*\n)", content, re.DOTALL)
    if fm_match:
        frontmatter = fm_match.group(1)
        body = content[fm_match.end():]

    # Extract blocks for each tier up to the requested level
    parts = [frontmatter]

    for tier in range(1, level + 1):
        start_marker, end_marker = _TIER_MARKERS[tier]
        # Find block between markers
        pattern = re.escape(start_marker) + r"\s*\n(.*?)\n\s*" + re.escape(end_marker)
        match = re.search(pattern, body, re.DOTALL)
        if match:
            parts.append(match.group(1).strip())

    result = "\n\n".join(p for p in parts if p.strip())
    return result.rstrip() + "\n" if result.strip() else content


def has_tier_markers(content: str) -> bool:
    """Check if content has any progressive disclosure tier markers."""
    return any(
        start in content
        for start, _ in _TIER_MARKERS.values()
    )


def count_tier_markers(content: str) -> int:
    """Count how many complete tier marker pairs (START + END) exist."""
    count = 0
    for start, end in _TIER_MARKERS.values():
        if start in content and end in content:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

def extract_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from a SKILL.md file.

    Returns a flat dict of frontmatter fields. Handles:
    - Simple key: value pairs
    - Multi-line description (>) continuation
    - Nested metadata block (flattened to metadata.key)
    - List values in brackets (e.g. dependencies: [a, b])

    Returns empty dict if no frontmatter found.
    """
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    raw = match.group(1)
    result: dict[str, str | list[str]] = {}
    current_key = ""
    in_metadata = False

    for line in raw.splitlines():
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # Detect nested block (e.g. metadata:)
        if re.match(r"^\w+:\s*$", line) and not line.startswith(" "):
            key = line.strip().rstrip(":")
            if key == "metadata":
                in_metadata = True
                continue
            current_key = key
            result[key] = ""
            continue

        # Metadata nested values: "  author: repoforge"
        if in_metadata and line.startswith("  ") and ":" in stripped:
            k, _, v = stripped.partition(":")
            result[f"metadata.{k.strip()}"] = v.strip().strip('"').strip("'")
            continue

        # End of metadata block (non-indented line)
        if in_metadata and not line.startswith(" "):
            in_metadata = False

        # Top-level key: value
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()

            # Handle block scalar indicator (>)
            if val == ">":
                current_key = key
                result[key] = ""
                continue

            # Handle list in brackets: [a, b, c]
            list_match = re.match(r"^\[(.*)\]$", val)
            if list_match:
                items = [i.strip().strip('"').strip("'") for i in list_match.group(1).split(",")]
                result[key] = [i for i in items if i]
                current_key = key
                continue

            # Simple value
            result[key] = val.strip('"').strip("'")
            current_key = key
            continue

        # Continuation line (indented, part of previous key)
        if line.startswith("  ") and current_key and current_key in result:
            existing = result[current_key]
            if isinstance(existing, str):
                sep = " " if existing else ""
                result[current_key] = existing + sep + stripped
            continue

    return result


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def estimate_tokens(content: str) -> int:
    """Rough token estimation (chars / 4).

    This is a simple heuristic. Actual token counts vary by model,
    but chars/4 is a reasonable approximation for English text with code.
    """
    return len(content) // 4


# ---------------------------------------------------------------------------
# Discovery index
# ---------------------------------------------------------------------------

def build_discovery_index(skills_dir: str) -> str:
    """Build a lightweight discovery index from all skills in a directory.

    Returns a markdown document with an L1-level summary of each skill:
    Name, Description, Trigger, Complexity, Token Estimate, Load Priority.

    This is what agents should load FIRST before deciding which full skills to read.

    Args:
        skills_dir: Path to directory containing SKILL.md files (recursive).

    Returns:
        Markdown string with the discovery index.
    """
    root = Path(skills_dir)
    skills: list[dict] = []

    for skill_path in sorted(root.rglob("SKILL.md")):
        try:
            content = skill_path.read_text(encoding="utf-8")
        except OSError as e:
            # File read error (permissions, encoding, etc.)
            logger.debug("Failed to read skill file %s: %s", skill_path, e)
            continue

        fm = extract_frontmatter(content)
        if not fm:
            continue

        # Derive relative path for display
        try:
            rel = str(skill_path.relative_to(root))
        except ValueError:
            rel = str(skill_path)

        # Extract trigger from description
        desc = fm.get("description", "")
        if isinstance(desc, str):
            trigger = ""
            trigger_match = re.search(r"Trigger:\s*(.+?)(?:\.|$)", desc, re.IGNORECASE)
            if trigger_match:
                trigger = trigger_match.group(1).strip()
            # Clean description (remove trigger line)
            clean_desc = re.sub(r"\s*Trigger:.*$", "", desc, flags=re.IGNORECASE).strip()
        else:
            clean_desc = str(desc)
            trigger = ""

        skills.append({
            "name": fm.get("name", skill_path.parent.name),
            "description": clean_desc,
            "trigger": trigger,
            "complexity": fm.get("complexity", "—"),
            "token_estimate": fm.get("token_estimate", str(estimate_tokens(content))),
            "load_priority": fm.get("load_priority", "—"),
            "path": rel,
        })

    # Build markdown
    lines = [
        "# Skill Discovery Index\n",
        "",
        "> Load this file FIRST. Then load full skills only when needed.",
        "> Each skill supports tiered loading: L1 (discovery) → L2 (quick ref) → L3 (full).",
        "",
        "| Name | Description | Trigger | Complexity | ~Tokens | Priority | Path |",
        "|------|-------------|---------|------------|---------|----------|------|",
    ]

    for s in skills:
        lines.append(
            f"| {s['name']} "
            f"| {s['description'][:60]}{'…' if len(s['description']) > 60 else ''} "
            f"| {s['trigger'][:50]}{'…' if len(s['trigger']) > 50 else ''} "
            f"| {s['complexity']} "
            f"| {s['token_estimate']} "
            f"| {s['load_priority']} "
            f"| `{s['path']}` |"
        )

    lines.append("")
    lines.append(f"**Total skills**: {len(skills)}")
    lines.append(f"**Index tokens**: ~{estimate_tokens(chr(10).join(lines))}")
    lines.append("")
    lines.append("## How to Use")
    lines.append("")
    lines.append("1. Scan this index to find relevant skills by trigger or description")
    lines.append("2. Load the skill at L1 or L2 level first (if tiered markers present)")
    lines.append("3. Only load full L3 content when you need deep examples or anti-patterns")
    lines.append("")

    return "\n".join(lines) + "\n"
