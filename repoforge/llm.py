"""
llm.py - Single LLM abstraction over LiteLLM.

Supports any provider LiteLLM supports:
  - Anthropic   (claude-haiku-3-5, claude-sonnet-4-5, ...)
  - OpenAI      (gpt-4o-mini, gpt-4o, ...)
  - GitHub Models (same models, different base_url + token)
  - Groq        (llama-3.1-70b-versatile, ...)
  - Ollama      (qwen2.5-coder:14b, llama3.2, deepseek-coder-v2, ...)
  - Google      (gemini-1.5-flash, ...)
  - Mistral     (mistral-small, ...)
  - Any OpenAI-compatible endpoint

Usage:
    llm = build_llm()                           # auto from env
    llm = build_llm("claude-haiku-3-5")        # explicit model
    llm = build_llm("ollama/qwen2.5-coder:14b")  # local
    llm = build_llm("groq/llama-3.1-70b-versatile")

    response = llm.complete("Your prompt here")
    # or streaming:
    for chunk in llm.stream("Your prompt"):
        print(chunk, end="", flush=True)
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Iterator
import litellm


# Silence LiteLLM's verbose success logging
litellm.success_callback = []
litellm.set_verbose = False


# ---------------------------------------------------------------------------
# Provider presets - sensible defaults per provider
# ---------------------------------------------------------------------------

PROVIDER_PRESETS = {
    # Format: "prefix_in_model_name": {defaults}
    "claude": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "fallback_api_key_env": "ANTHROPIC_AUTH_TOKEN",  # codeviewx compat
        "max_tokens": 4096,
        "temperature": 0.0,
    },
    "gpt": {
        "api_key_env": "OPENAI_API_KEY",
        "max_tokens": 4096,
        "temperature": 0.0,
    },
    "o1": {
        "api_key_env": "OPENAI_API_KEY",
        "max_tokens": 4096,
        "temperature": 1,  # o1 doesn't support 0
    },
    "gemini": {
        "api_key_env": "GEMINI_API_KEY",
        "max_tokens": 4096,
        "temperature": 0.0,
    },
    "groq": {
        "api_key_env": "GROQ_API_KEY",
        "max_tokens": 4096,
        "temperature": 0.0,
    },
    "ollama": {
        "api_key_env": None,  # no key needed
        "max_tokens": 4096,
        "temperature": 0.0,
        "api_base": None,  # reads OLLAMA_BASE_URL or default
    },
    "github": {
        "api_key_env": "GITHUB_TOKEN",
        "api_base": "https://models.inference.ai.azure.com",
        "max_tokens": 4096,
        "temperature": 0.0,
    },
    "mistral": {
        "api_key_env": "MISTRAL_API_KEY",
        "max_tokens": 4096,
        "temperature": 0.0,
    },
}

# Default model if nothing is configured
DEFAULT_MODEL = "claude-haiku-3-5"

# Auto-detection order from env vars
AUTO_DETECT_ORDER = [
    ("ANTHROPIC_API_KEY", "claude-haiku-3-5"),
    ("ANTHROPIC_AUTH_TOKEN", "claude-haiku-3-5"),
    ("OPENAI_API_KEY", "gpt-4o-mini"),
    ("GROQ_API_KEY", "groq/llama-3.1-70b-versatile"),
    ("GITHUB_TOKEN", "github/gpt-4o-mini"),
    ("GEMINI_API_KEY", "gemini/gemini-1.5-flash"),
    ("MISTRAL_API_KEY", "mistral/mistral-small"),
]


# ---------------------------------------------------------------------------
# LLM wrapper
# ---------------------------------------------------------------------------

@dataclass
class LLM:
    model: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.0
    extra_kwargs: dict = field(default_factory=dict)

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        """Single-shot completion. Returns the full response string."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs = self._base_kwargs()
        response = litellm.completion(messages=messages, **kwargs)
        return response.choices[0].message.content or ""

    def stream(self, prompt: str, system: Optional[str] = None) -> Iterator[str]:
        """Streaming completion. Yields string chunks."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs = self._base_kwargs()
        kwargs["stream"] = True

        for chunk in litellm.completion(messages=messages, **kwargs):
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    def _base_kwargs(self) -> dict:
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            **self.extra_kwargs,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        return kwargs


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_llm(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> LLM:
    """
    Build an LLM instance.

    Model string format (LiteLLM convention):
        "claude-haiku-3-5"                  -> Anthropic
        "gpt-4o-mini"                       -> OpenAI
        "groq/llama-3.1-70b-versatile"      -> Groq
        "ollama/qwen2.5-coder:14b"          -> Ollama local
        "github/gpt-4o-mini"                -> GitHub Models
        "gemini/gemini-1.5-flash"           -> Google
        "mistral/mistral-small"             -> Mistral

    If model is None, auto-detects from available env vars.
    """
    # Auto-detect if no model specified
    if not model:
        model = _auto_detect_model()

    # Normalize: "github/gpt-4o-mini" -> prefix="github"
    prefix = model.split("/")[0].lower()

    preset = _find_preset(prefix)

    # Resolve API key
    resolved_key = api_key
    if not resolved_key and preset.get("api_key_env"):
        resolved_key = os.getenv(preset["api_key_env"])
    if not resolved_key and preset.get("fallback_api_key_env"):
        resolved_key = os.getenv(preset["fallback_api_key_env"])

    # Resolve API base
    resolved_base = api_base or preset.get("api_base")
    if prefix == "ollama" and not resolved_base:
        resolved_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    if prefix == "github" and not resolved_base:
        resolved_base = "https://models.inference.ai.azure.com"
        # GitHub Models uses openai/ prefix in litellm
        if not model.startswith("openai/") and not model.startswith("github/"):
            model = f"openai/{model.split('/', 1)[-1]}"

    return LLM(
        model=model,
        api_key=resolved_key,
        api_base=resolved_base,
        max_tokens=max_tokens or preset.get("max_tokens", 4096),
        temperature=temperature if temperature is not None else preset.get("temperature", 0.0),
    )


def _auto_detect_model() -> str:
    for env_var, model in AUTO_DETECT_ORDER:
        if os.getenv(env_var):
            return model
    # Last resort: try ollama
    return "ollama/qwen2.5-coder:14b"


def _find_preset(prefix: str) -> dict:
    # Exact match first
    if prefix in PROVIDER_PRESETS:
        return PROVIDER_PRESETS[prefix]
    # Prefix match (e.g. "claude-3" matches "claude")
    for key in PROVIDER_PRESETS:
        if prefix.startswith(key):
            return PROVIDER_PRESETS[key]
    return {"max_tokens": 4096, "temperature": 0.0}
