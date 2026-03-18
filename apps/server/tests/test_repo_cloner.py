"""Tests for the repo cloner URL validation."""

import pytest

from app.services.repo_cloner import _validate_url


def test_valid_github_url():
    """Standard GitHub URL should be accepted and normalized."""
    result = _validate_url("https://github.com/owner/repo")
    assert result == "https://github.com/owner/repo"


def test_valid_github_url_with_trailing_slash():
    """Trailing slashes should be stripped."""
    result = _validate_url("https://github.com/owner/repo/")
    assert result == "https://github.com/owner/repo"


def test_valid_github_url_with_query_params():
    """Query parameters should be stripped."""
    result = _validate_url("https://github.com/owner/repo?tab=readme")
    assert result == "https://github.com/owner/repo"


def test_valid_github_url_with_hash():
    """Hash fragments should be stripped."""
    result = _validate_url("https://github.com/owner/repo#readme")
    assert result == "https://github.com/owner/repo"


def test_reject_non_github_url():
    """Non-GitHub URLs should be rejected."""
    with pytest.raises(ValueError, match="Invalid repository URL"):
        _validate_url("https://gitlab.com/owner/repo")


def test_reject_http_url():
    """HTTP (non-HTTPS) URLs should be rejected."""
    with pytest.raises(ValueError, match="Invalid repository URL"):
        _validate_url("http://github.com/owner/repo")


def test_reject_github_subpath():
    """URLs with extra path segments should be rejected."""
    with pytest.raises(ValueError, match="Invalid repository URL"):
        _validate_url("https://github.com/owner/repo/tree/main")


def test_reject_empty_string():
    """Empty string should be rejected."""
    with pytest.raises(ValueError, match="Invalid repository URL"):
        _validate_url("")


def test_reject_random_string():
    """Random non-URL strings should be rejected."""
    with pytest.raises(ValueError, match="Invalid repository URL"):
        _validate_url("not-a-url-at-all")


def test_valid_url_with_dots_and_hyphens():
    """Owner/repo names with dots and hyphens should be valid."""
    result = _validate_url("https://github.com/my-org/my.repo-name")
    assert result == "https://github.com/my-org/my.repo-name"
