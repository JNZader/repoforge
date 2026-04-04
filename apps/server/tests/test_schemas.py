"""Tests for Pydantic request/response schemas."""

import pytest
from app.models.schemas import GenerateRequest
from pydantic import ValidationError


def _make_request(**overrides) -> dict:
    """Build a valid GenerateRequest dict with optional overrides."""
    defaults = {
        "repo_url": "https://github.com/owner/repo",
        "mode": "docs",
        "model": "gpt-4o-mini",
        "provider": "openai",
    }
    defaults.update(overrides)
    return defaults


def test_valid_generate_request():
    """A well-formed request should validate successfully."""
    req = GenerateRequest(**_make_request())
    assert req.repo_url == "https://github.com/owner/repo"
    assert req.mode == "docs"
    assert req.language == "English"  # default


def test_valid_github_url_with_trailing_slash():
    """Trailing slashes should be normalized."""
    req = GenerateRequest(**_make_request(repo_url="https://github.com/owner/repo/"))
    assert req.repo_url == "https://github.com/owner/repo"


def test_reject_non_github_url():
    """Non-GitHub URLs should be rejected."""
    with pytest.raises(ValidationError, match="GitHub repository URL"):
        GenerateRequest(**_make_request(repo_url="https://gitlab.com/owner/repo"))


def test_reject_invalid_url():
    """Random strings should be rejected as URLs."""
    with pytest.raises(ValidationError):
        GenerateRequest(**_make_request(repo_url="not-a-url"))


def test_mode_docs():
    """Mode 'docs' should be accepted."""
    req = GenerateRequest(**_make_request(mode="docs"))
    assert req.mode == "docs"


def test_mode_skills():
    """Mode 'skills' should be accepted."""
    req = GenerateRequest(**_make_request(mode="skills"))
    assert req.mode == "skills"


def test_mode_both():
    """Mode 'both' should be accepted."""
    req = GenerateRequest(**_make_request(mode="both"))
    assert req.mode == "both"


def test_invalid_mode():
    """Invalid mode values should be rejected."""
    with pytest.raises(ValidationError):
        GenerateRequest(**_make_request(mode="invalid"))


def test_empty_repo_url():
    """Empty repo_url should be rejected."""
    with pytest.raises(ValidationError):
        GenerateRequest(**_make_request(repo_url=""))


def test_optional_fields_defaults():
    """Optional fields should have sensible defaults."""
    req = GenerateRequest(**_make_request())
    assert req.language == "English"
    assert req.complexity == "auto"
    assert req.options is None


def test_custom_language():
    """Custom language should be accepted."""
    req = GenerateRequest(**_make_request(language="Spanish"))
    assert req.language == "Spanish"


def test_url_with_query_params_stripped():
    """Query params in the URL should be stripped during validation."""
    req = GenerateRequest(**_make_request(repo_url="https://github.com/owner/repo?tab=code"))
    assert "?" not in req.repo_url
