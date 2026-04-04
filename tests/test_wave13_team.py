"""Tests for Wave 13: Team features — config profiles, style enforcement."""

import pytest

from repoforge.profiles import (
    PROFILES,
    ProfileConfig,
    apply_profile,
    get_profile,
)
from repoforge.style import (
    DEFAULT_RULES,
    StyleRule,
    StyleViolation,
    check_style,
)

# ── Config profiles ──────────────────────────────────────────────────────


class TestProfileRegistry:

    def test_builtin_profiles_exist(self):
        assert "fastapi" in PROFILES
        assert "cli" in PROFILES
        assert "library" in PROFILES
        assert "monorepo" in PROFILES

    def test_all_profiles_are_dataclass(self):
        for name, profile in PROFILES.items():
            assert isinstance(profile, ProfileConfig)
            assert profile.name == name

    def test_get_profile_by_name(self):
        p = get_profile("fastapi")
        assert p.name == "fastapi"

    def test_get_profile_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown profile"):
            get_profile("wordpress")

    def test_each_profile_has_project_type(self):
        for name, p in PROFILES.items():
            assert p.project_type, f"{name} missing project_type"


class TestProfileConfig:

    def test_fastapi_profile(self):
        p = get_profile("fastapi")
        assert p.project_type == "web_service"
        assert p.default_persona is not None

    def test_cli_profile(self):
        p = get_profile("cli")
        assert p.project_type == "cli_tool"

    def test_library_profile(self):
        p = get_profile("library")
        assert p.project_type == "library_sdk"


class TestApplyProfile:

    def test_applies_project_type(self):
        base = {"complexity": "auto"}
        result = apply_profile("fastapi", base)
        assert result["project_type"] == "web_service"

    def test_applies_default_persona(self):
        result = apply_profile("fastapi", {})
        assert "persona" in result

    def test_preserves_existing_config(self):
        base = {"language": "Spanish", "model": "gpt-4o"}
        result = apply_profile("cli", base)
        assert result["language"] == "Spanish"
        assert result["model"] == "gpt-4o"

    def test_none_profile_passes_through(self):
        base = {"language": "English"}
        result = apply_profile(None, base)
        assert result == base

    def test_config_overrides_profile_defaults(self):
        base = {"persona": "architect"}
        result = apply_profile("fastapi", base)
        # User's explicit choice wins
        assert result["persona"] == "architect"

    def test_applies_recommended_chapters(self):
        result = apply_profile("fastapi", {})
        assert "recommended_chapters" in result


# ── Style enforcement ────────────────────────────────────────────────────


class TestDefaultRules:

    def test_has_rules(self):
        assert len(DEFAULT_RULES) >= 3

    def test_all_rules_have_name(self):
        for rule in DEFAULT_RULES:
            assert isinstance(rule, StyleRule)
            assert rule.name


class TestCheckStyle:

    def test_good_doc_passes(self):
        good = """# Architecture

## Overview

The system uses a layered architecture with clear separation of concerns.

## Components

Each component handles a specific responsibility.

## Data Flow

Data flows from the API layer through services to the store.
"""
        violations = check_style(good)
        # Good doc should have few or no violations
        assert isinstance(violations, list)

    def test_heading_without_content_flagged(self):
        bad = """# Title

## Section 1

## Section 2

## Section 3
"""
        violations = check_style(bad)
        names = [v.rule for v in violations]
        assert "empty_section" in names

    def test_very_long_paragraph_flagged(self):
        long_para = "Word " * 200 + "end."
        content = f"# Title\n\n{long_para}\n"
        violations = check_style(content)
        names = [v.rule for v in violations]
        assert "long_paragraph" in names

    def test_no_heading_flagged(self):
        violations = check_style("Just some text without any heading.")
        names = [v.rule for v in violations]
        assert "missing_h1" in names

    def test_violation_has_fields(self):
        violations = check_style("No heading here.")
        assert len(violations) >= 1
        v = violations[0]
        assert hasattr(v, "rule")
        assert hasattr(v, "message")
        assert hasattr(v, "severity")

    def test_empty_content(self):
        violations = check_style("")
        assert isinstance(violations, list)
