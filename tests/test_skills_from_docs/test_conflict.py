"""Tests for skills_from_docs.conflict module."""

from pathlib import Path

import pytest

from repoforge.skills_from_docs.conflict import (
    _extract_rules,
    _rules_conflict,
    check_conflicts,
)


class TestExtractRules:
    def test_numbered_rules(self):
        text = (
            "## Critical Rules\n\n"
            "1. Always use type annotations\n"
            "2. Prefer composition over inheritance\n"
            "3. Never use eval()\n"
        )
        rules = _extract_rules(text)
        assert len(rules) == 3
        assert "Always use type annotations" in rules[0]

    def test_bullet_rules_in_section(self):
        text = (
            "## Critical Patterns\n\n"
            "- Use strict mode\n"
            "- Prefer const over let\n"
        )
        rules = _extract_rules(text)
        assert len(rules) == 2

    def test_no_rules(self):
        text = "# Just a title\n\nSome regular content.\n"
        rules = _extract_rules(text)
        assert len(rules) == 0


class TestRulesConflict:
    def test_opposing_always_never(self):
        assert _rules_conflict(
            "Always use class components",
            "Never use class components",
        )

    def test_opposing_prefer_avoid(self):
        assert _rules_conflict(
            "Prefer mutable state objects",
            "Avoid mutable state objects",
        )

    def test_no_conflict_different_subjects(self):
        assert not _rules_conflict(
            "Always use TypeScript",
            "Never eat pizza at midnight",
        )

    def test_no_conflict_same_direction(self):
        assert not _rules_conflict(
            "Always use strict mode",
            "Always use strict mode in all files",
        )


class TestCheckConflicts:
    def test_detects_conflict(self, tmp_path):
        # Create an existing skill
        skill_dir = tmp_path / "existing-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: existing-skill\n---\n\n"
            "## Critical Rules\n\n"
            "1. Always use class-based components\n"
            "2. Prefer OOP patterns\n"
        )

        # Generated skill that contradicts
        generated = (
            "---\nname: new-skill\n---\n\n"
            "## Critical Rules\n\n"
            "1. Never use class-based components\n"
            "2. Prefer functional patterns\n"
        )

        conflicts = check_conflicts(generated, str(tmp_path))
        assert len(conflicts) >= 1
        assert any("class" in c.description.lower() for c in conflicts)

    def test_no_conflicts(self, tmp_path):
        skill_dir = tmp_path / "existing-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: existing-skill\n---\n\n"
            "## Critical Rules\n\n"
            "1. Use Python 3.10+\n"
        )

        generated = (
            "---\nname: new-skill\n---\n\n"
            "## Critical Rules\n\n"
            "1. Use TypeScript strict mode\n"
        )

        conflicts = check_conflicts(generated, str(tmp_path))
        assert len(conflicts) == 0

    def test_nonexistent_dir(self):
        conflicts = check_conflicts("some skill content", "/nonexistent")
        assert conflicts == []

    def test_no_rules_in_generated(self, tmp_path):
        skill_dir = tmp_path / "existing"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: existing\n---\n\nJust text.\n")

        conflicts = check_conflicts("Just text, no rules.", str(tmp_path))
        assert conflicts == []
