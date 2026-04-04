"""Tests for Wave 1: LLM Gateway provider (mcp-llm-bridge compatibility)."""

import os

import pytest

from repoforge.llm import AUTO_DETECT_ORDER, _auto_detect_model, build_llm

# ── gateway provider ─────────────────────────────────────────────────────


class TestGatewayProvider:

    def test_model_rewritten_to_openai_prefix(self):
        llm = build_llm("gateway/claude-sonnet-4")
        assert llm.model == "openai/claude-sonnet-4"

    def test_default_api_base_is_localhost(self):
        llm = build_llm("gateway/claude-sonnet-4")
        assert llm.api_base == "http://localhost:3456/v1"

    def test_gateway_url_env_overrides_default(self, monkeypatch):
        monkeypatch.setenv("LLM_GATEWAY_URL", "https://gateway.example.com/v1")
        llm = build_llm("gateway/gpt-4o")
        assert llm.api_base == "https://gateway.example.com/v1"

    def test_auth_token_used_as_api_key(self, monkeypatch):
        monkeypatch.setenv("LLM_GATEWAY_AUTH_TOKEN", "sk-secret-gateway-123")
        llm = build_llm("gateway/gpt-4o")
        assert llm.api_key == "sk-secret-gateway-123"

    def test_no_auth_token_resolves_none(self):
        # No LLM_GATEWAY_AUTH_TOKEN set → api_key should be None
        llm = build_llm("gateway/gpt-4o")
        assert llm.api_key is None

    def test_x_project_header_in_extra_kwargs(self):
        llm = build_llm("gateway/claude-sonnet-4")
        assert "extra_headers" in llm.extra_kwargs
        assert llm.extra_kwargs["extra_headers"]["X-Project"] == "repoforge"

    def test_any_model_name_passes_through(self):
        llm = build_llm("gateway/some-random-model-v99")
        assert llm.model == "openai/some-random-model-v99"

    def test_temperature_preserved(self):
        llm = build_llm("gateway/gpt-4o")
        assert llm.temperature == 0.0


# ── auto-detect order ────────────────────────────────────────────────────


class TestAutoDetectOrder:

    def test_gateway_is_last(self):
        last_env, last_model = AUTO_DETECT_ORDER[-1]
        assert last_env == "LLM_GATEWAY_AUTH_TOKEN"
        assert last_model.startswith("gateway/")

    def test_github_comes_before_gateway(self):
        env_vars = [entry[0] for entry in AUTO_DETECT_ORDER]
        github_idx = env_vars.index("GITHUB_TOKEN")
        gateway_idx = env_vars.index("LLM_GATEWAY_AUTH_TOKEN")
        assert github_idx < gateway_idx

    def test_auto_detect_picks_github_not_gateway(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
        model = _auto_detect_model()
        # _auto_detect_model returns a string like "github/gpt-4o-mini"
        assert model.startswith("github/")

    def test_auto_detect_prefers_anthropic_over_all(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-123")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_123")
        monkeypatch.setenv("LLM_GATEWAY_AUTH_TOKEN", "gw-123")
        model = _auto_detect_model()
        assert model.startswith("claude")

    def test_auto_detect_gateway_when_only_gateway(self, monkeypatch):
        monkeypatch.setenv("LLM_GATEWAY_AUTH_TOKEN", "gw-only")
        model = _auto_detect_model()
        assert model.startswith("gateway/")
        # Verify the full round-trip through build_llm
        llm = build_llm(model)
        assert llm.model.startswith("openai/")
        assert llm.api_base == "http://localhost:3456/v1"


# ── regression: existing providers unchanged ─────────────────────────────


class TestExistingProviders:

    def test_github_provider(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        llm = build_llm("github/gpt-4o-mini")
        assert llm.api_base == "https://models.inference.ai.azure.com"
        assert llm.api_key == "ghp_test"

    def test_ollama_provider(self):
        llm = build_llm("ollama/qwen2.5-coder:14b")
        assert "localhost" in (llm.api_base or "")

    def test_explicit_model_ignores_env(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        llm = build_llm("gateway/gpt-4o")
        # Even with GITHUB_TOKEN set, explicit gateway/ should use gateway
        assert llm.api_base == "http://localhost:3456/v1"
