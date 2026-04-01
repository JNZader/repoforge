"""
conflict.py - Conflict detection between generated and existing skills.

Compares a generated SKILL.md against existing installed skills
and warns when contradictions are detected.

Deterministic — no LLM needed.
"""

import logging
import re
from pathlib import Path

from .types import SkillConflict

logger = logging.getLogger(__name__)

# Patterns that suggest opposing recommendations
_OPPOSITION_PAIRS = [
    (r"\balways\s+use\b", r"\bnever\s+use\b"),
    (r"\bprefer\b", r"\bavoid\b"),
    (r"\bdo\b", r"\bdon'?t\b"),
    (r"\bshould\b", r"\bshould\s+not\b"),
    (r"\bmust\b", r"\bmust\s+not\b"),
    (r"\brecommend\b", r"\bdeprecated?\b"),
]


def _extract_rules(skill_text: str) -> list[str]:
    """Extract rule-like statements from a SKILL.md."""
    rules: list[str] = []
    in_rules_section = False

    for line in skill_text.split("\n"):
        stripped = line.strip()

        # Track if we're in a rules/patterns section
        if re.match(r"^#{1,3}\s+.*(?:rule|pattern|practice|convention)", stripped, re.IGNORECASE):
            in_rules_section = True
            continue
        elif re.match(r"^#{1,3}\s+", stripped):
            in_rules_section = False
            continue

        # Numbered rules: "1. Always use ..."
        if re.match(r"^\d+\.\s+", stripped):
            rules.append(re.sub(r"^\d+\.\s+", "", stripped))
        # Bullet rules in rules sections
        elif in_rules_section and re.match(r"^[-*]\s+", stripped):
            rules.append(re.sub(r"^[-*]\s+", "", stripped))

    return rules


def _extract_skill_name(skill_text: str) -> str:
    """Extract skill name from YAML frontmatter."""
    match = re.search(r"^name:\s*(.+)$", skill_text, re.MULTILINE)
    return match.group(1).strip() if match else "unknown"


def _extract_subjects(text: str) -> set[str]:
    """Extract key subject words from a rule (nouns after verbs)."""
    # Remove common verbs and extract what remains
    cleaned = re.sub(
        r"\b(?:always|never|avoid|use|prefer|do|don't|should|must|not|the|a|an|to|for|with|in|on|of|is|are|it|when|if|that|this|and|or|but)\b",
        " ",
        text.lower(),
    )
    words = {w for w in re.findall(r"\b\w{3,}\b", cleaned)}
    return words


def _rules_conflict(rule_a: str, rule_b: str) -> bool:
    """Check if two rules appear to contradict each other.

    Heuristic: rules conflict if they share subject matter but have
    opposing directive verbs (e.g., "always use X" vs "never use X").
    """
    # Must share at least one meaningful subject word
    subjects_a = _extract_subjects(rule_a)
    subjects_b = _extract_subjects(rule_b)
    common = subjects_a & subjects_b

    if len(common) < 1:
        return False

    # Check for opposition patterns
    for pos_re, neg_re in _OPPOSITION_PAIRS:
        a_pos = bool(re.search(pos_re, rule_a, re.IGNORECASE))
        a_neg = bool(re.search(neg_re, rule_a, re.IGNORECASE))
        b_pos = bool(re.search(pos_re, rule_b, re.IGNORECASE))
        b_neg = bool(re.search(neg_re, rule_b, re.IGNORECASE))

        # One says positive, other says negative
        if (a_pos and b_neg) or (a_neg and b_pos):
            return True

    return False


def check_conflicts(
    generated_skill: str,
    existing_dir: str,
) -> list[SkillConflict]:
    """Compare a generated SKILL.md against existing skills in a directory.

    Args:
        generated_skill: Content of the generated SKILL.md.
        existing_dir: Path to directory containing existing SKILL.md files.

    Returns:
        List of detected conflicts.
    """
    conflicts: list[SkillConflict] = []
    existing_path = Path(existing_dir)

    if not existing_path.is_dir():
        return conflicts

    generated_rules = _extract_rules(generated_skill)
    if not generated_rules:
        return conflicts

    # Scan existing skills
    for skill_file in sorted(existing_path.rglob("SKILL.md")):
        try:
            existing_text = skill_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        existing_name = _extract_skill_name(existing_text)
        existing_rules = _extract_rules(existing_text)

        for gen_rule in generated_rules:
            for exist_rule in existing_rules:
                if _rules_conflict(gen_rule, exist_rule):
                    conflicts.append(
                        SkillConflict(
                            existing_skill=f"{existing_name} ({skill_file})",
                            generated_rule=gen_rule,
                            existing_rule=exist_rule,
                            description=(
                                f"Generated rule may contradict existing skill "
                                f"'{existing_name}': "
                                f"generated says '{gen_rule[:80]}' "
                                f"but existing says '{exist_rule[:80]}'"
                            ),
                        )
                    )

    return conflicts
