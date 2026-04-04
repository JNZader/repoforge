"""
tests/test_llm_integration.py — Integration tests for the LLM abstraction layer.

Tests everything EXCEPT the actual API call (litellm.completion is mocked).
Exercises: factory, provider detection, config resolution, message building,
response parsing, error handling.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from repoforge.llm import (
    AUTO_DETECT_ORDER,
    DEFAULT_MODEL,  # noqa: F401
    LLM,
    PROVIDER_PRESETS,  # noqa: F401
    _auto_detect_model,
    _find_preset,
    _is_reasoning_model,
    build_llm,
)

# ---------------------------------------------------------------------------
# LLM dataclass
# ---------------------------------------------------------------------------

class TestLLMDataclass:
    def test_defaults(self):
        llm = LLM(model="test-model")
        assert llm.model == "test-model"
        assert llm.api_key is None
        assert llm.api_base is None
        assert llm.max_tokens == 4096
        assert llm.temperature == 0.0
        assert llm.extra_kwargs == {}

    def test_custom_values(self):
        llm = LLM(
            model="gpt-4o",
            api_key="sk-test",
            api_base="https://custom.api.com",
            max_tokens=2048,
            temperature=0.5,
            extra_kwargs={"top_p": 0.9},
        )
        assert llm.model == "gpt-4o"
        assert llm.api_key == "sk-test"
        assert llm.api_base == "https://custom.api.com"
        assert llm.max_tokens == 2048
        assert llm.temperature == 0.5
        assert llm.extra_kwargs == {"top_p": 0.9}


# ---------------------------------------------------------------------------
# _base_kwargs
# ---------------------------------------------------------------------------

class TestBaseKwargs:
    def test_minimal_kwargs(self):
        llm = LLM(model="test-model")
        kwargs = llm._base_kwargs()
        assert kwargs["model"] == "test-model"
        assert kwargs["max_tokens"] == 4096
        assert kwargs["temperature"] == 0.0
        assert "api_key" not in kwargs
        assert "api_base" not in kwargs

    def test_includes_api_key(self):
        llm = LLM(model="test", api_key="key123")
        kwargs = llm._base_kwargs()
        assert kwargs["api_key"] == "key123"

    def test_includes_api_base(self):
        llm = LLM(model="test", api_base="https://base.url")
        kwargs = llm._base_kwargs()
        assert kwargs["api_base"] == "https://base.url"

    def test_merges_extra_kwargs(self):
        llm = LLM(model="test", extra_kwargs={"top_p": 0.8, "seed": 42})
        kwargs = llm._base_kwargs()
        assert kwargs["top_p"] == 0.8
        assert kwargs["seed"] == 42


# ---------------------------------------------------------------------------
# complete() and stream()
# ---------------------------------------------------------------------------

class TestComplete:
    @patch("repoforge.llm.litellm.completion")
    def test_complete_basic(self, mock_completion):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello, world!"
        mock_completion.return_value = mock_response

        llm = LLM(model="test-model")
        result = llm.complete("Say hello")

        assert result == "Hello, world!"
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args
        messages = call_kwargs.kwargs.get("messages", call_kwargs[1].get("messages"))
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Say hello"

    @patch("repoforge.llm.litellm.completion")
    def test_complete_with_system(self, mock_completion):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Done"
        mock_completion.return_value = mock_response

        llm = LLM(model="test-model")
        result = llm.complete("Do this", system="You are a helper")

        messages = mock_completion.call_args.kwargs.get(
            "messages", mock_completion.call_args[1].get("messages")
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helper"
        assert messages[1]["role"] == "user"

    @patch("repoforge.llm.litellm.completion")
    def test_complete_none_content_returns_empty(self, mock_completion):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_completion.return_value = mock_response

        llm = LLM(model="test-model")
        result = llm.complete("Hello")
        assert result == ""

    @patch("repoforge.llm.litellm.completion")
    def test_complete_passes_kwargs(self, mock_completion):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        mock_completion.return_value = mock_response

        llm = LLM(
            model="test-model",
            api_key="key",
            api_base="https://base",
            max_tokens=1024,
            temperature=0.7,
        )
        llm.complete("test")

        call_kwargs = mock_completion.call_args.kwargs
        assert call_kwargs["model"] == "test-model"
        assert call_kwargs["api_key"] == "key"
        assert call_kwargs["api_base"] == "https://base"
        assert call_kwargs["max_tokens"] == 1024
        assert call_kwargs["temperature"] == 0.7


class TestStream:
    @patch("repoforge.llm.litellm.completion")
    def test_stream_basic(self, mock_completion):
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta = MagicMock()
        chunk1.choices[0].delta.content = "Hello"

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta = MagicMock()
        chunk2.choices[0].delta.content = " world"

        mock_completion.return_value = iter([chunk1, chunk2])

        llm = LLM(model="test-model")
        chunks = list(llm.stream("Say hello"))

        assert chunks == ["Hello", " world"]
        call_kwargs = mock_completion.call_args.kwargs
        assert call_kwargs["stream"] is True

    @patch("repoforge.llm.litellm.completion")
    def test_stream_skips_empty_deltas(self, mock_completion):
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta = MagicMock()
        chunk1.choices[0].delta.content = "Hi"

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta = None

        chunk3 = MagicMock()
        chunk3.choices = [MagicMock()]
        chunk3.choices[0].delta = MagicMock()
        chunk3.choices[0].delta.content = None

        mock_completion.return_value = iter([chunk1, chunk2, chunk3])

        llm = LLM(model="test-model")
        chunks = list(llm.stream("Hello"))
        assert chunks == ["Hi"]

    @patch("repoforge.llm.litellm.completion")
    def test_stream_with_system(self, mock_completion):
        mock_completion.return_value = iter([])
        llm = LLM(model="test-model")
        list(llm.stream("Hello", system="Be helpful"))

        messages = mock_completion.call_args.kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"


# ---------------------------------------------------------------------------
# _find_preset
# ---------------------------------------------------------------------------

class TestFindPreset:
    def test_exact_match_claude(self):
        preset = _find_preset("claude")
        assert preset["api_key_env"] == "ANTHROPIC_API_KEY"

    def test_exact_match_gpt(self):
        preset = _find_preset("gpt")
        assert preset["api_key_env"] == "OPENAI_API_KEY"

    def test_exact_match_groq(self):
        preset = _find_preset("groq")
        assert preset["api_key_env"] == "GROQ_API_KEY"

    def test_exact_match_ollama(self):
        preset = _find_preset("ollama")
        assert preset["api_key_env"] is None

    def test_exact_match_github(self):
        preset = _find_preset("github")
        assert preset["api_key_env"] == "GITHUB_TOKEN"
        assert "azure" in preset["api_base"]

    def test_prefix_match(self):
        preset = _find_preset("claude-3")
        assert preset["api_key_env"] == "ANTHROPIC_API_KEY"

    def test_unknown_returns_defaults(self):
        preset = _find_preset("unknown-provider")
        assert preset["max_tokens"] == 4096
        assert preset["temperature"] == 0.0

    def test_gemini_preset(self):
        preset = _find_preset("gemini")
        assert preset["api_key_env"] == "GEMINI_API_KEY"

    def test_mistral_preset(self):
        preset = _find_preset("mistral")
        assert preset["api_key_env"] == "MISTRAL_API_KEY"


# ---------------------------------------------------------------------------
# _auto_detect_model
# ---------------------------------------------------------------------------

class TestAutoDetectModel:
    def test_detects_anthropic(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake"}, clear=False):
            model = _auto_detect_model()
            assert "claude" in model

    def test_detects_openai(self):
        env = {k: "" for k, _ in AUTO_DETECT_ORDER}
        env["OPENAI_API_KEY"] = "fake"
        # Clear anthropic keys so openai is detected
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        with patch.dict(os.environ, env, clear=True):
            # Ensure anthropic vars are not set
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
            model = _auto_detect_model()
            assert "gpt" in model

    def test_fallback_to_ollama(self):
        # Clear all detection env vars
        with patch.dict(os.environ, {}, clear=True):
            model = _auto_detect_model()
            assert "ollama" in model


# ---------------------------------------------------------------------------
# build_llm factory
# ---------------------------------------------------------------------------

class TestBuildLLM:
    def test_explicit_model(self):
        llm = build_llm(model="gpt-4o-mini", api_key="test-key")
        assert llm.model == "gpt-4o-mini"
        assert llm.api_key == "test-key"

    def test_claude_model_gets_preset(self):
        llm = build_llm(model="claude-haiku-3-5", api_key="test-key")
        assert llm.temperature == 0.0
        assert llm.max_tokens == 4096

    def test_ollama_model_gets_base_url(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OLLAMA_BASE_URL", None)
            llm = build_llm(model="ollama/qwen2.5-coder:14b")
            assert llm.api_base == "http://localhost:11434"

    def test_ollama_respects_custom_base_url(self):
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://gpu:11434"}):
            llm = build_llm(model="ollama/qwen2.5-coder:14b")
            assert llm.api_base == "http://gpu:11434"

    def test_github_model_gets_azure_base(self):
        llm = build_llm(model="github/gpt-4o-mini", api_key="ghp_test")
        assert "azure" in llm.api_base

    def test_api_key_from_env(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            llm = build_llm(model="claude-haiku-3-5")
            assert llm.api_key == "env-key"

    def test_explicit_api_key_overrides_env(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            llm = build_llm(model="claude-haiku-3-5", api_key="explicit")
            assert llm.api_key == "explicit"

    def test_custom_max_tokens(self):
        llm = build_llm(model="gpt-4o-mini", max_tokens=8192, api_key="k")
        assert llm.max_tokens == 8192

    def test_custom_temperature(self):
        llm = build_llm(model="gpt-4o-mini", temperature=0.5, api_key="k")
        assert llm.temperature == 0.5

    def test_fallback_api_key_env(self):
        with patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "fallback-key"}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            llm = build_llm(model="claude-haiku-3-5")
            assert llm.api_key == "fallback-key"

    def test_auto_detect_when_no_model(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "groq-key"}, clear=True):
            llm = build_llm()
            assert "groq" in llm.model

    def test_o1_model_temperature(self):
        preset = _find_preset("o1")
        assert preset["temperature"] == 1.0  # reasoning models reject 0


# ---------------------------------------------------------------------------
# Error simulation
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @patch("repoforge.llm.litellm.completion")
    def test_api_error_propagates(self, mock_completion):
        mock_completion.side_effect = Exception("API rate limit exceeded")
        llm = LLM(model="test-model")
        with pytest.raises(Exception, match="rate limit"):
            llm.complete("Hello")

    @patch("repoforge.llm.litellm.completion")
    def test_stream_error_propagates(self, mock_completion):
        def failing_stream(**kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="start"))])
            raise ConnectionError("Connection lost")

        mock_completion.return_value = failing_stream()
        llm = LLM(model="test-model")
        with pytest.raises(ConnectionError):
            list(llm.stream("Hello"))

    @patch("repoforge.llm.litellm.completion")
    def test_timeout_error(self, mock_completion):
        mock_completion.side_effect = TimeoutError("Request timed out")
        llm = LLM(model="test-model")
        with pytest.raises(TimeoutError):
            llm.complete("Hello")


# ---------------------------------------------------------------------------
# _is_reasoning_model
# ---------------------------------------------------------------------------

class TestIsReasoningModel:
    def test_deepseek_r1(self):
        assert _is_reasoning_model("DeepSeek-R1") is True

    def test_deepseek_r1_lowercase(self):
        assert _is_reasoning_model("deepseek-r1") is True

    def test_o1_model(self):
        assert _is_reasoning_model("o1") is True

    def test_o1_mini(self):
        assert _is_reasoning_model("o1-mini") is True

    def test_o3_model(self):
        assert _is_reasoning_model("o3") is True

    def test_o3_mini(self):
        assert _is_reasoning_model("o3-mini") is True

    def test_gpt4o_is_not_reasoning(self):
        assert _is_reasoning_model("gpt-4o") is False

    def test_llama_is_not_reasoning(self):
        assert _is_reasoning_model("Meta-Llama-3.1-405B-Instruct") is False

    def test_phi4_is_not_reasoning(self):
        assert _is_reasoning_model("Phi-4") is False


# ---------------------------------------------------------------------------
# GitHub Models — all 6 models
# ---------------------------------------------------------------------------

class TestGitHubModels:
    """Verify build_llm resolves all GitHub Models correctly."""

    GITHUB_MODELS = [
        "github/gpt-4o",
        "github/gpt-4o-mini",
        "github/DeepSeek-R1",
        "github/Meta-Llama-3.1-405B-Instruct",
        "github/Phi-4",
        "github/Meta-Llama-3.1-8B-Instruct",
    ]

    @pytest.mark.parametrize("model", GITHUB_MODELS)
    def test_github_model_resolves_api_base(self, model):
        llm = build_llm(model=model, api_key="ghp_test")
        assert llm.api_base == "https://models.inference.ai.azure.com"

    @pytest.mark.parametrize("model", GITHUB_MODELS)
    def test_github_model_preserves_model_string(self, model):
        llm = build_llm(model=model, api_key="ghp_test")
        assert llm.model == model

    @pytest.mark.parametrize("model", GITHUB_MODELS)
    def test_github_model_resolves_api_key_from_env(self, model):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_env_token"}):
            llm = build_llm(model=model)
            assert llm.api_key == "ghp_env_token"

    def test_deepseek_r1_gets_reasoning_temperature(self):
        llm = build_llm(model="github/DeepSeek-R1", api_key="ghp_test")
        assert llm.temperature == 1.0

    def test_gpt4o_gets_default_temperature(self):
        llm = build_llm(model="github/gpt-4o", api_key="ghp_test")
        assert llm.temperature == 0.0

    def test_llama_gets_default_temperature(self):
        llm = build_llm(model="github/Meta-Llama-3.1-405B-Instruct", api_key="ghp_test")
        assert llm.temperature == 0.0

    def test_phi4_gets_default_temperature(self):
        llm = build_llm(model="github/Phi-4", api_key="ghp_test")
        assert llm.temperature == 0.0

    def test_explicit_temperature_overrides_reasoning_default(self):
        llm = build_llm(model="github/DeepSeek-R1", api_key="ghp_test", temperature=0.5)
        assert llm.temperature == 0.5

    @patch("repoforge.llm.litellm.completion")
    def test_github_deepseek_r1_calls_litellm_correctly(self, mock_completion):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        mock_completion.return_value = mock_response

        llm = build_llm(model="github/DeepSeek-R1", api_key="ghp_test")
        llm.complete("say ok")

        call_kwargs = mock_completion.call_args.kwargs
        assert call_kwargs["model"] == "github/DeepSeek-R1"
        assert call_kwargs["api_base"] == "https://models.inference.ai.azure.com"
        assert call_kwargs["api_key"] == "ghp_test"
        assert call_kwargs["temperature"] == 1.0

    @patch("repoforge.llm.litellm.completion")
    def test_github_phi4_calls_litellm_correctly(self, mock_completion):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        mock_completion.return_value = mock_response

        llm = build_llm(model="github/Phi-4", api_key="ghp_test")
        llm.complete("say ok")

        call_kwargs = mock_completion.call_args.kwargs
        assert call_kwargs["model"] == "github/Phi-4"
        assert call_kwargs["api_base"] == "https://models.inference.ai.azure.com"
        assert call_kwargs["temperature"] == 0.0


# ---------------------------------------------------------------------------
# Reasoning model temperature — cross-provider
# ---------------------------------------------------------------------------

class TestReasoningModelTemperature:
    """Reasoning models get temperature=1.0 automatically across providers."""

    def test_o1_via_build_llm(self):
        llm = build_llm(model="o1", api_key="sk-test")
        assert llm.temperature == 1.0

    def test_o1_mini_via_build_llm(self):
        llm = build_llm(model="o1-mini", api_key="sk-test")
        assert llm.temperature == 1.0

    def test_o3_mini_via_build_llm(self):
        llm = build_llm(model="o3-mini", api_key="sk-test")
        assert llm.temperature == 1.0

    def test_explicit_temperature_not_overridden(self):
        llm = build_llm(model="o1", api_key="sk-test", temperature=0.7)
        assert llm.temperature == 0.7
