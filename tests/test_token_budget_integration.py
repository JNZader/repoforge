"""
tests/test_token_budget_integration.py — Tests for token budget enforcement in _generate.

Verifies that prompts exceeding the input token budget are truncated before
reaching the LLM, and that warnings are logged on truncation.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from repoforge.generator import (
    _CHARS_PER_TOKEN,
    _DEFAULT_INPUT_TOKEN_BUDGET,
    _estimate_prompt_tokens,
    _generate,
)
from repoforge.llm import LLM

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llm() -> LLM:
    """Build a mock LLM that records calls instead of hitting an API."""
    llm = LLM(model="test-model")
    llm.complete = MagicMock(return_value="LLM response")
    return llm


# ---------------------------------------------------------------------------
# _estimate_prompt_tokens
# ---------------------------------------------------------------------------


class TestEstimatePromptTokens:
    """Token estimation uses ~4 chars/token, consistent with budget.py."""

    def test_empty_string(self):
        assert _estimate_prompt_tokens("") == 1  # min 1

    def test_known_length(self):
        text = "x" * 400  # 400 chars -> 100 tokens
        assert _estimate_prompt_tokens(text) == 100

    def test_short_string(self):
        assert _estimate_prompt_tokens("hi") == 1  # 2 chars / 4 = 0 -> min 1

    def test_consistent_with_budget_module(self):
        """Same formula as intelligence.budget._estimate_tokens."""
        from repoforge.intelligence.budget import _estimate_tokens
        text = "a" * 1000
        assert _estimate_prompt_tokens(text) == _estimate_tokens(text)


# ---------------------------------------------------------------------------
# _generate with budget enforcement
# ---------------------------------------------------------------------------


class TestGenerateBudgetEnforcement:
    """_generate truncates user prompt when total tokens exceed input_budget."""

    def test_under_budget_no_truncation(self):
        """Prompts within budget are passed through unchanged."""
        llm = _make_llm()
        system = "System instructions"
        user = "User request"

        result = _generate(llm, system, user, dry_run=False, input_budget=10_000)

        assert result == "LLM response"
        llm.complete.assert_called_once_with(user, system=system)

    def test_over_budget_truncates_user_prompt(self):
        """User prompt is truncated when total tokens exceed budget."""
        llm = _make_llm()
        system = "S" * 40  # 10 tokens
        user = "U" * 4000  # 1000 tokens -> total 1010, budget 500

        _generate(llm, system, user, dry_run=False, input_budget=500)

        # The user prompt passed to LLM should be shorter than original
        actual_user = llm.complete.call_args[0][0]
        assert len(actual_user) < len(user)
        # Total should fit within budget
        total = _estimate_prompt_tokens(system) + _estimate_prompt_tokens(actual_user)
        assert total <= 500

    def test_over_budget_logs_warning(self, caplog):
        """A warning is logged when truncation occurs."""
        llm = _make_llm()
        system = "S" * 40  # 10 tokens
        user = "U" * 4000  # 1000 tokens

        with caplog.at_level(logging.WARNING, logger="repoforge.generator"):
            _generate(llm, system, user, dry_run=False, input_budget=500)

        assert any("Token budget exceeded" in msg for msg in caplog.messages)
        assert any("truncated" in msg.lower() for msg in caplog.messages)

    def test_system_prompt_never_truncated(self):
        """System prompt is preserved intact even when over budget."""
        llm = _make_llm()
        system = "SYSTEM " * 100  # system is ~175 tokens
        user = "U" * 4000  # 1000 tokens

        _generate(llm, system, user, dry_run=False, input_budget=200)

        actual_system = llm.complete.call_args[1]["system"]
        assert actual_system == system  # system unchanged

    def test_budget_equals_system_tokens_empties_user(self):
        """When budget equals system token count, user prompt becomes empty."""
        llm = _make_llm()
        system = "S" * 400  # 100 tokens
        user = "U" * 4000  # 1000 tokens

        _generate(llm, system, user, dry_run=False, input_budget=100)

        actual_user = llm.complete.call_args[0][0]
        assert actual_user == ""

    def test_dry_run_skips_budget_check(self):
        """Dry run returns placeholder without checking budget."""
        llm = _make_llm()
        system = "S" * 1_000_000
        user = "U" * 1_000_000

        result = _generate(llm, system, user, dry_run=True, input_budget=10)

        assert "DRY RUN" in result
        llm.complete.assert_not_called()

    def test_default_budget_is_120k(self):
        """The default input token budget is 120,000."""
        assert _DEFAULT_INPUT_TOKEN_BUDGET == 120_000

    def test_exact_budget_no_truncation(self):
        """Prompt exactly at budget is not truncated."""
        llm = _make_llm()
        budget = 100
        system = "S" * (50 * _CHARS_PER_TOKEN)  # 50 tokens
        user = "U" * (50 * _CHARS_PER_TOKEN)  # 50 tokens -> total 100 = budget

        _generate(llm, system, user, dry_run=False, input_budget=budget)

        actual_user = llm.complete.call_args[0][0]
        assert actual_user == user  # no truncation


class TestGenerateBudgetEdgeCases:
    """Edge cases for budget enforcement."""

    def test_empty_prompts(self):
        """Empty system and user prompts work fine."""
        llm = _make_llm()
        result = _generate(llm, "", "", dry_run=False, input_budget=100)
        assert result == "LLM response"

    def test_very_small_budget(self):
        """Budget of 1 token still calls LLM (with truncated prompt)."""
        llm = _make_llm()
        _generate(llm, "system", "user prompt", dry_run=False, input_budget=1)
        llm.complete.assert_called_once()

    def test_truncated_content_is_prefix(self):
        """Truncation preserves the beginning of the user prompt."""
        llm = _make_llm()
        user = "AAAA" + "B" * 4000  # starts with AAAA, then lots of B
        system = ""

        _generate(llm, system, user, dry_run=False, input_budget=10)

        actual_user = llm.complete.call_args[0][0]
        assert actual_user.startswith("AAAA")
