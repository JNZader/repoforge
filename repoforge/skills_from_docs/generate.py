"""
generate.py - SKILL.md generation from extracted documentation content.

Produces well-structured SKILL.md files with YAML frontmatter
matching the Gentleman-Skills / repoforge format.

Deterministic — no LLM needed.
"""

import re
from typing import Optional

from .types import CodeExample, DocContent


def _to_kebab_case(text: str) -> str:
    """Convert text to kebab-case for skill names."""
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:50]


def _build_frontmatter(name: str, title: str, source: str) -> str:
    """Build YAML frontmatter block."""
    # Escape YAML special chars in description
    desc = f"Patterns and best practices from {title} documentation."
    trigger = f"When working with {title} concepts or APIs."

    return (
        "---\n"
        f"name: {name}\n"
        f"description: >\n"
        f"  {desc}\n"
        f"  Trigger: {trigger}\n"
        f"license: Apache-2.0\n"
        f"metadata:\n"
        f"  author: repoforge\n"
        f'  version: "1.0"\n'
        f"  source: {source}\n"
        "---\n"
    )


def _build_critical_patterns(doc: DocContent) -> str:
    """Build the Critical Patterns section from extracted content."""
    lines: list[str] = ["## Critical Patterns\n"]

    # Group code examples by context (heading they appeared under)
    examples_by_context: dict[str, list[CodeExample]] = {}
    for ex in doc.code_examples[:10]:  # cap at 10 examples
        examples_by_context.setdefault(ex.context, []).append(ex)

    if examples_by_context:
        for context, examples in examples_by_context.items():
            lines.append(f"### {context}\n")
            for ex in examples[:3]:  # max 3 per context
                lines.append(f"```{ex.language}")
                lines.append(ex.code)
                lines.append("```\n")
    elif doc.sections:
        # No code examples — use section content as patterns
        for section in doc.sections[:5]:
            if section.level >= 2:
                lines.append(f"### {section.heading}\n")
                # Truncate long content
                content = section.content
                if len(content) > 500:
                    content = content[:500] + "..."
                lines.append(f"{content}\n")

    return "\n".join(lines)


def _build_critical_rules(doc: DocContent) -> str:
    """Build the Critical Rules section from patterns and anti-patterns."""
    lines: list[str] = ["## Critical Rules\n"]

    rule_num = 1

    # Patterns as DO rules
    for pattern in doc.patterns[:8]:
        lines.append(f"{rule_num}. {pattern}")
        rule_num += 1

    # Anti-patterns as DON'T rules
    for anti in doc.anti_patterns[:5]:
        lines.append(f"{rule_num}. {anti}")
        rule_num += 1

    if rule_num == 1:
        # No patterns extracted — add generic rules from sections
        for section in doc.sections[:3]:
            if section.content and len(section.content) > 20:
                # Extract first meaningful sentence
                sentence = section.content.split(".")[0].strip()
                if sentence and len(sentence) > 10:
                    lines.append(f"{rule_num}. {sentence}.")
                    rule_num += 1
                    if rule_num > 5:
                        break

    return "\n".join(lines)


def _build_key_concepts(doc: DocContent) -> str:
    """Build a Key Concepts section from top-level sections."""
    lines: list[str] = ["## Key Concepts\n"]

    # Use level-2 headings as concepts
    concepts = [s for s in doc.sections if s.level == 2][:8]
    if not concepts:
        concepts = [s for s in doc.sections if s.level <= 3][:8]

    if not concepts:
        return ""

    for section in concepts:
        lines.append(f"### {section.heading}\n")
        # First paragraph only
        content = section.content.split("\n\n")[0].strip()
        if len(content) > 300:
            content = content[:300] + "..."
        lines.append(f"{content}\n")

    return "\n".join(lines)


def generate_skill_md(
    doc: DocContent,
    name: Optional[str] = None,
) -> str:
    """Generate a SKILL.md string from extracted DocContent.

    Args:
        doc: Extracted documentation content.
        name: Override skill name (kebab-case). Auto-derived from title if None.

    Returns:
        Complete SKILL.md content string.
    """
    if not name:
        name = _to_kebab_case(doc.title)
    else:
        name = _to_kebab_case(name)

    parts: list[str] = []

    # YAML frontmatter
    parts.append(_build_frontmatter(name, doc.title, doc.source))

    # Critical Patterns (with code examples)
    critical = _build_critical_patterns(doc)
    if critical.count("\n") > 2:  # more than just the header
        parts.append(critical)

    # Key Concepts
    concepts = _build_key_concepts(doc)
    if concepts:
        parts.append(concepts)

    # Critical Rules
    rules = _build_critical_rules(doc)
    if rules.count("\n") > 1:  # more than just the header
        parts.append(rules)

    return "\n".join(parts) + "\n"
