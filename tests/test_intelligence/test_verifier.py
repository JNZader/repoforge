"""Tests for repoforge.intelligence.verifier — Stage C LLM verification."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from repoforge.facts import FactItem
from repoforge.intelligence.ast_extractor import ASTSymbol
from repoforge.intelligence.verifier import (
    DEFAULT_VERIFIER_MODEL,
    FALLBACK_VERIFIER_MODEL,
    _apply_verification_corrections,
    _build_verification_prompt,
    _format_facts_for_verification,
    _parse_verification_response,
    _resolve_verifier_model,
    verify_chapter,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _fact(fact_type: str, value: str, file: str = "server.go", line: int = 10) -> FactItem:
    return FactItem(fact_type=fact_type, value=value, file=file, line=line, language="Go")


def _symbol(name: str, kind: str = "function", signature: str = "") -> ASTSymbol:
    return ASTSymbol(
        name=name, kind=kind,
        signature=signature or f"func {name}()",
        file="server.go", line=1,
    )


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------

class TestResolveVerifierModel:
    def test_explicit_model_used_as_is(self):
        assert _resolve_verifier_model("gpt-4o", "anything") == "gpt-4o"

    def test_default_is_phi4(self):
        assert _resolve_verifier_model(None, "github/gpt-4o-mini") == DEFAULT_VERIFIER_MODEL

    def test_fallback_when_generator_is_phi4(self):
        assert _resolve_verifier_model(None, "github/Phi-4") == FALLBACK_VERIFIER_MODEL

    def test_fallback_when_generator_is_phi4_lowercase(self):
        assert _resolve_verifier_model(None, "github/phi-4") == FALLBACK_VERIFIER_MODEL


# ---------------------------------------------------------------------------
# Facts formatting
# ---------------------------------------------------------------------------

class TestFormatFacts:
    def test_formats_facts_by_type(self):
        facts = [_fact("port", "7437"), _fact("endpoint", "GET /health")]
        result = _format_facts_for_verification(facts, None)
        assert "PORT" in result
        assert "7437" in result
        assert "ENDPOINT" in result
        assert "/health" in result

    def test_includes_ast_symbols(self):
        facts = [_fact("port", "7437")]
        symbols = {"server.go": [_symbol("New", "function", "func New(store *Store) *Server")]}
        result = _format_facts_for_verification(facts, symbols)
        assert "KEY SYMBOLS" in result
        assert "func New(store *Store) *Server" in result

    def test_empty_facts_returns_placeholder(self):
        result = _format_facts_for_verification([], None)
        assert "no facts available" in result

    def test_caps_symbols_at_50(self):
        symbols = {
            f"file{i}.go": [_symbol(f"Func{i}", "function", f"func Func{i}()")]
            for i in range(60)
        }
        result = _format_facts_for_verification([], symbols)
        # Should contain at most 50 symbol lines
        sym_lines = [l for l in result.split("\n") if l.startswith("- func")]
        assert len(sym_lines) <= 50


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_prompt_contains_chapter_and_facts(self):
        prompt = _build_verification_prompt("# My Chapter", "### PORT\n- 7437")
        assert "My Chapter" in prompt
        assert "7437" in prompt
        assert "VERIFIED FACTS" in prompt
        assert "JSON array" in prompt


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

class TestParseResponse:
    def test_parses_clean_json(self):
        raw = json.dumps([
            {"type": "wrong", "claim": "port 8080", "correction": "port 7437", "evidence": "fact: port=7437"},
            {"type": "ok", "claim": "uses Go"},
        ])
        result = _parse_verification_response(raw)
        assert len(result) == 2
        assert result[0]["type"] == "wrong"

    def test_parses_json_with_markdown_fences(self):
        raw = "```json\n" + json.dumps([{"type": "ok", "claim": "correct"}]) + "\n```"
        result = _parse_verification_response(raw)
        assert len(result) == 1

    def test_parses_json_embedded_in_text(self):
        raw = "Here are the results:\n" + json.dumps([{"type": "ok", "claim": "good"}]) + "\nDone."
        result = _parse_verification_response(raw)
        assert len(result) == 1

    def test_returns_empty_for_garbage(self):
        result = _parse_verification_response("this is not json at all")
        assert result == []

    def test_returns_empty_for_json_object(self):
        result = _parse_verification_response('{"type": "wrong"}')
        assert result == []


# ---------------------------------------------------------------------------
# Correction application
# ---------------------------------------------------------------------------

class TestApplyCorrections:
    def test_applies_wrong_correction(self):
        content = "The server runs on port 8080."
        corrections = [
            {"type": "wrong", "claim": "port 8080", "correction": "port 7437", "evidence": "fact: port=7437"},
        ]
        result, issues = _apply_verification_corrections(content, corrections)
        assert "port 7437" in result
        assert "port 8080" not in result
        assert len(issues) == 1
        assert "FIXED" in issues[0]

    def test_flags_unfindable_wrong_claim(self):
        content = "The server runs on port 7437."
        corrections = [
            {"type": "wrong", "claim": "port 9999", "correction": "port 7437", "evidence": ""},
        ]
        result, issues = _apply_verification_corrections(content, corrections)
        assert result == content  # unchanged
        assert len(issues) == 1
        assert "FLAGGED" in issues[0]

    def test_logs_missing_facts(self):
        content = "# API"
        corrections = [
            {"type": "missing", "fact": "POST /api/save", "suggestion": "add endpoint docs"},
        ]
        result, issues = _apply_verification_corrections(content, corrections)
        assert result == content  # missing doesn't modify content
        assert len(issues) == 1
        assert "MISSING" in issues[0]

    def test_ok_type_is_no_op(self):
        content = "All good."
        corrections = [{"type": "ok", "claim": "all good"}]
        result, issues = _apply_verification_corrections(content, corrections)
        assert result == content
        assert len(issues) == 0

    def test_handles_non_dict_items(self):
        content = "Some text."
        corrections = ["garbage", None, 42]
        result, issues = _apply_verification_corrections(content, corrections)
        assert result == content
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Full verify_chapter (mocked LLM)
# ---------------------------------------------------------------------------

class TestVerifyChapter:
    @patch("repoforge.intelligence.verifier.build_llm")
    def test_applies_corrections_from_llm(self, mock_build_llm):
        mock_verifier = MagicMock()
        mock_verifier.complete.return_value = json.dumps([
            {"type": "wrong", "claim": "port 8080", "correction": "port 7437", "evidence": "port fact"},
        ])
        mock_build_llm.return_value = mock_verifier

        generator_llm = MagicMock()
        generator_llm.model = "github/gpt-4o-mini"

        content = "The server runs on port 8080."
        facts = [_fact("port", "7437")]

        result, issues = verify_chapter(content, facts, None, generator_llm)
        assert "port 7437" in result
        assert len(issues) == 1

    @patch("repoforge.intelligence.verifier.build_llm")
    def test_returns_original_on_llm_error(self, mock_build_llm):
        mock_verifier = MagicMock()
        mock_verifier.complete.side_effect = RuntimeError("API error")
        mock_build_llm.return_value = mock_verifier

        generator_llm = MagicMock()
        generator_llm.model = "github/gpt-4o-mini"

        content = "Original content."
        result, issues = verify_chapter(content, [], None, generator_llm)
        assert result == content
        assert len(issues) == 1
        assert "error" in issues[0].lower()

    @patch("repoforge.intelligence.verifier.build_llm")
    def test_uses_phi4_by_default(self, mock_build_llm):
        mock_verifier = MagicMock()
        mock_verifier.complete.return_value = '[{"type": "ok", "claim": "good"}]'
        mock_build_llm.return_value = mock_verifier

        generator_llm = MagicMock()
        generator_llm.model = "github/gpt-4o-mini"

        verify_chapter("content", [], None, generator_llm)
        mock_build_llm.assert_called_once_with(model="github/Phi-4")

    @patch("repoforge.intelligence.verifier.build_llm")
    def test_avoids_phi4_self_review(self, mock_build_llm):
        mock_verifier = MagicMock()
        mock_verifier.complete.return_value = '[{"type": "ok", "claim": "good"}]'
        mock_build_llm.return_value = mock_verifier

        generator_llm = MagicMock()
        generator_llm.model = "github/Phi-4"

        verify_chapter("content", [], None, generator_llm)
        mock_build_llm.assert_called_once_with(model="github/gpt-4o-mini")
