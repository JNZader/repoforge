"""Validate provider API keys against their real APIs.

Each provider has a lightweight validation call that checks if the key is
valid without incurring significant cost.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

_VALIDATION_TIMEOUT = 10.0  # seconds


async def validate_provider_key(
    provider: str,
    api_key: str,
) -> tuple[bool, list[str]]:
    """Validate an API key against the provider's real API.

    Args:
        provider: Provider name (``openai``, ``anthropic``, ``google``,
                  ``groq``, ``mistral``, ``github-models``).
        api_key: The API key to validate.

    Returns:
        Tuple of ``(is_valid, available_models)``. On failure,
        ``is_valid`` is ``False`` and ``available_models`` is empty.
    """
    handler = _PROVIDER_VALIDATORS.get(provider)
    if handler is None:
        logger.warning("No validator for provider: %s", provider)
        return False, []

    try:
        return await handler(api_key)
    except httpx.TimeoutException:
        logger.warning("Validation timeout for provider %s", provider)
        return False, []
    except Exception:
        logger.exception("Unexpected error validating %s key", provider)
        return False, []


# ---------- Per-provider validators ----------


async def _validate_openai(api_key: str) -> tuple[bool, list[str]]:
    """Validate OpenAI key via GET /v1/models."""
    async with httpx.AsyncClient(timeout=_VALIDATION_TIMEOUT) as client:
        resp = await client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
    if resp.status_code != 200:
        return False, []
    data = resp.json()
    models = [m["id"] for m in data.get("data", [])]
    return True, models


async def _validate_anthropic(api_key: str) -> tuple[bool, list[str]]:
    """Validate Anthropic key via POST /v1/messages with a minimal payload."""
    async with httpx.AsyncClient(timeout=_VALIDATION_TIMEOUT) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    # 200 means the key works; we don't care about the actual response content
    if resp.status_code == 200:
        return True, ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"]
    return False, []


async def _validate_google(api_key: str) -> tuple[bool, list[str]]:
    """Validate Google AI key via GET /v1/models."""
    async with httpx.AsyncClient(timeout=_VALIDATION_TIMEOUT) as client:
        resp = await client.get(
            "https://generativelanguage.googleapis.com/v1/models",
            params={"key": api_key},
        )
    if resp.status_code != 200:
        return False, []
    data = resp.json()
    models = [m.get("name", "") for m in data.get("models", [])]
    return True, models


async def _validate_groq(api_key: str) -> tuple[bool, list[str]]:
    """Validate Groq key via GET /openai/v1/models."""
    async with httpx.AsyncClient(timeout=_VALIDATION_TIMEOUT) as client:
        resp = await client.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
    if resp.status_code != 200:
        return False, []
    data = resp.json()
    models = [m["id"] for m in data.get("data", [])]
    return True, models


async def _validate_mistral(api_key: str) -> tuple[bool, list[str]]:
    """Validate Mistral key via GET /v1/models."""
    async with httpx.AsyncClient(timeout=_VALIDATION_TIMEOUT) as client:
        resp = await client.get(
            "https://api.mistral.ai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
    if resp.status_code != 200:
        return False, []
    data = resp.json()
    models = [m["id"] for m in data.get("data", [])]
    return True, models


async def _validate_github_models(api_key: str) -> tuple[bool, list[str]]:
    """Validate GitHub PAT against the Models inference API.

    Uses a minimal completion call to verify the token can access inference.
    OAuth tokens with read:user scope will fail here (by design).
    """
    async with httpx.AsyncClient(timeout=_VALIDATION_TIMEOUT) as client:
        resp = await client.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
            },
        )
    if resp.status_code == 200:
        return True, ["gpt-4o-mini", "gpt-4o"]
    logger.warning(
        "GitHub Models validation failed (status=%d). "
        "Make sure you're using a PAT, not an OAuth token.",
        resp.status_code,
    )
    return False, []


_PROVIDER_VALIDATORS = {
    "openai": _validate_openai,
    "anthropic": _validate_anthropic,
    "google": _validate_google,
    "groq": _validate_groq,
    "mistral": _validate_mistral,
    "github-models": _validate_github_models,
}
