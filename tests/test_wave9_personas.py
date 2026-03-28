"""Tests for Wave 9: Persona-adaptive documentation prompts."""

import pytest

from repoforge.personas import (
    Persona,
    PERSONAS,
    get_persona,
    apply_persona,
)


# ── Persona registry ─────────────────────────────────────────────────────


class TestPersonaRegistry:

    def test_builtin_personas_exist(self):
        assert "beginner" in PERSONAS
        assert "contributor" in PERSONAS
        assert "architect" in PERSONAS
        assert "api-consumer" in PERSONAS

    def test_all_personas_are_dataclass(self):
        for name, persona in PERSONAS.items():
            assert isinstance(persona, Persona)
            assert persona.name == name

    def test_get_persona_by_name(self):
        p = get_persona("beginner")
        assert p.name == "beginner"

    def test_get_persona_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown persona"):
            get_persona("ceo")

    def test_each_persona_has_required_fields(self):
        for name, p in PERSONAS.items():
            assert p.name, f"{name} missing name"
            assert p.description, f"{name} missing description"
            assert p.system_modifier, f"{name} missing system_modifier"
            assert p.focus_areas, f"{name} missing focus_areas"


# ── Persona fields ───────────────────────────────────────────────────────


class TestPersonaContent:

    def test_beginner_focuses_on_getting_started(self):
        p = get_persona("beginner")
        combined = p.system_modifier + " ".join(p.focus_areas)
        assert any(w in combined.lower() for w in ["step", "beginner", "simple", "example"])

    def test_architect_focuses_on_design(self):
        p = get_persona("architect")
        combined = p.system_modifier + " ".join(p.focus_areas)
        assert any(w in combined.lower() for w in ["architecture", "design", "pattern", "tradeoff"])

    def test_api_consumer_focuses_on_api(self):
        p = get_persona("api-consumer")
        combined = p.system_modifier + " ".join(p.focus_areas)
        assert any(w in combined.lower() for w in ["api", "endpoint", "request", "response"])

    def test_contributor_focuses_on_code(self):
        p = get_persona("contributor")
        combined = p.system_modifier + " ".join(p.focus_areas)
        assert any(w in combined.lower() for w in ["contribut", "code", "test", "develop"])


# ── apply_persona ────────────────────────────────────────────────────────


class TestApplyPersona:

    def test_modifies_system_prompt(self):
        base_system = "You are a technical writer."
        base_user = "Generate overview docs."
        result = apply_persona("beginner", base_system, base_user)
        assert result["system"] != base_system
        assert "beginner" in result["system"].lower() or "step" in result["system"].lower()

    def test_modifies_user_prompt(self):
        base_system = "You are a technical writer."
        base_user = "Generate overview docs."
        result = apply_persona("architect", base_system, base_user)
        assert "focus" in result["user"].lower() or "architect" in result["user"].lower()

    def test_none_persona_passes_through(self):
        base_system = "You are a technical writer."
        base_user = "Generate docs."
        result = apply_persona(None, base_system, base_user)
        assert result["system"] == base_system
        assert result["user"] == base_user

    def test_returns_dict_with_system_and_user(self):
        result = apply_persona("beginner", "sys", "usr")
        assert "system" in result
        assert "user" in result

    def test_preserves_original_content(self):
        result = apply_persona("contributor", "Base system.", "Generate overview.")
        # Original content should still be present
        assert "Base system" in result["system"]
        assert "Generate overview" in result["user"]
