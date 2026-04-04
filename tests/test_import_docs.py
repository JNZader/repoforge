"""Tests for repoforge.import_docs module."""

import json
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from repoforge.cli import main
from repoforge.import_docs import (
    _sanitize_name,
    fetch_github_docs,
    fetch_npm_readme,
    fetch_pypi_description,
    import_docs,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_urlopen(data: dict, status: int = 200):
    """Create a mock for urllib.request.urlopen returning JSON data."""
    body = json.dumps(data).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# Unit tests: _sanitize_name
# ---------------------------------------------------------------------------

class TestSanitizeName:
    def test_simple_name(self):
        assert _sanitize_name("react") == "react"

    def test_scoped_package(self):
        assert _sanitize_name("@angular/core") == "angular-core"

    def test_url_chars(self):
        assert _sanitize_name("https://github.com/org/repo") == "https-github.com-org-repo"

    def test_collapses_dashes(self):
        assert _sanitize_name("a///b") == "a-b"

    def test_strips_edge_dashes(self):
        assert _sanitize_name("@scope/") == "scope"

    def test_lowercases(self):
        assert _sanitize_name("MyPackage") == "mypackage"


# ---------------------------------------------------------------------------
# Unit tests: fetch_npm_readme
# ---------------------------------------------------------------------------

class TestFetchNpmReadme:
    @patch("repoforge.import_docs.urllib.request.urlopen")
    def test_returns_readme(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen({"readme": "# Hello\nWorld"})
        result = fetch_npm_readme("test-pkg")
        assert "# Hello" in result
        assert "World" in result

    @patch("repoforge.import_docs.urllib.request.urlopen")
    def test_fallback_to_description(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen({
            "readme": "ERROR: No README data found!",
            "description": "A test package",
        })
        result = fetch_npm_readme("test-pkg")
        assert "A test package" in result

    @patch("repoforge.import_docs.urllib.request.urlopen")
    def test_no_readme_no_description_raises(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen({
            "readme": "ERROR: No README data found!",
        })
        with pytest.raises(RuntimeError, match="No README found"):
            fetch_npm_readme("nonexistent")

    @patch("repoforge.import_docs.urllib.request.urlopen")
    def test_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://registry.npmjs.org/nope",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )
        with pytest.raises(RuntimeError, match="HTTP 404"):
            fetch_npm_readme("nope")


# ---------------------------------------------------------------------------
# Unit tests: fetch_pypi_description
# ---------------------------------------------------------------------------

class TestFetchPypiDescription:
    @patch("repoforge.import_docs.urllib.request.urlopen")
    def test_returns_description(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen({
            "info": {"description": "# Click\n\nCLI toolkit"},
        })
        result = fetch_pypi_description("click")
        assert "# Click" in result

    @patch("repoforge.import_docs.urllib.request.urlopen")
    def test_fallback_to_summary(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen({
            "info": {"description": "", "summary": "A CLI toolkit"},
        })
        result = fetch_pypi_description("click")
        assert "A CLI toolkit" in result

    @patch("repoforge.import_docs.urllib.request.urlopen")
    def test_no_description_raises(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen({"info": {}})
        with pytest.raises(RuntimeError, match="No description found"):
            fetch_pypi_description("nonexistent")

    @patch("repoforge.import_docs.urllib.request.urlopen")
    def test_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://pypi.org/pypi/nope/json",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )
        with pytest.raises(RuntimeError, match="HTTP 404"):
            fetch_pypi_description("nope")


# ---------------------------------------------------------------------------
# Unit tests: fetch_github_docs
# ---------------------------------------------------------------------------

class TestFetchGithubDocs:
    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Not a valid GitHub URL"):
            fetch_github_docs("not-a-url")

    @patch("repoforge.import_docs.subprocess.run")
    def test_clone_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="fatal: repo not found")
        with pytest.raises(RuntimeError, match="git clone failed"):
            fetch_github_docs("https://github.com/owner/repo")

    @patch("repoforge.import_docs.subprocess.run")
    @patch("repoforge.import_docs.tempfile.mkdtemp")
    def test_reads_readme(self, mock_mkdtemp, mock_run, tmp_path):
        mock_mkdtemp.return_value = str(tmp_path)
        mock_run.return_value = MagicMock(returncode=0)

        # Create a README in the tmp dir
        (tmp_path / "README.md").write_text("# My Repo\n\nSome docs.")

        result = fetch_github_docs("https://github.com/owner/repo")
        assert "# My Repo" in result

    @patch("repoforge.import_docs.subprocess.run")
    @patch("repoforge.import_docs.tempfile.mkdtemp")
    def test_reads_docs_dir(self, mock_mkdtemp, mock_run, tmp_path):
        mock_mkdtemp.return_value = str(tmp_path)
        mock_run.return_value = MagicMock(returncode=0)

        # Create README and docs/
        (tmp_path / "README.md").write_text("# Repo")
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("# Guide\n\nUsage info.")

        result = fetch_github_docs("https://github.com/owner/repo")
        assert "# Repo" in result
        assert "# Guide" in result

    @patch("repoforge.import_docs.subprocess.run")
    @patch("repoforge.import_docs.tempfile.mkdtemp")
    def test_no_docs_raises(self, mock_mkdtemp, mock_run, tmp_path):
        mock_mkdtemp.return_value = str(tmp_path)
        mock_run.return_value = MagicMock(returncode=0)
        # Empty repo — no README, no docs
        with pytest.raises(RuntimeError, match="No documentation found"):
            fetch_github_docs("https://github.com/owner/repo")


# ---------------------------------------------------------------------------
# Unit tests: import_docs orchestrator
# ---------------------------------------------------------------------------

class TestImportDocs:
    @patch("repoforge.import_docs.fetch_npm_readme", return_value="# React\n\nUI lib")
    def test_imports_npm(self, mock_fetch, tmp_path):
        result = import_docs(
            working_dir=str(tmp_path),
            npm=["react"],
        )
        assert result["total"] == 1
        assert len(result["imported"]) == 1
        assert "npm--react.md" in result["imported"][0]
        out_file = tmp_path / ".repoforge" / "external-docs" / "npm--react.md"
        assert out_file.exists()
        assert "# React" in out_file.read_text()

    @patch("repoforge.import_docs.fetch_pypi_description", return_value="# Click\n\nCLI")
    def test_imports_pypi(self, mock_fetch, tmp_path):
        result = import_docs(
            working_dir=str(tmp_path),
            pypi=["click"],
        )
        assert result["total"] == 1
        out_file = tmp_path / ".repoforge" / "external-docs" / "pypi--click.md"
        assert out_file.exists()

    @patch("repoforge.import_docs.fetch_github_docs", return_value="# Repo\n\nDocs")
    def test_imports_github(self, mock_fetch, tmp_path):
        result = import_docs(
            working_dir=str(tmp_path),
            github=["https://github.com/org/repo"],
        )
        assert result["total"] == 1
        out_file = tmp_path / ".repoforge" / "external-docs" / "github--org--repo.md"
        assert out_file.exists()

    @patch("repoforge.import_docs.fetch_npm_readme", side_effect=RuntimeError("fail"))
    def test_handles_failure_gracefully(self, mock_fetch, tmp_path):
        result = import_docs(
            working_dir=str(tmp_path),
            npm=["bad-pkg"],
        )
        assert result["total"] == 0
        assert len(result["failed"]) == 1
        assert "npm/bad-pkg" in result["failed"][0]["source"]

    @patch("repoforge.import_docs.fetch_npm_readme", return_value="# A")
    @patch("repoforge.import_docs.fetch_pypi_description", return_value="# B")
    def test_mixed_sources(self, mock_pypi, mock_npm, tmp_path):
        result = import_docs(
            working_dir=str(tmp_path),
            npm=["react"],
            pypi=["click"],
        )
        assert result["total"] == 2
        assert len(result["failed"]) == 0

    def test_creates_output_dir(self, tmp_path):
        """Output dir is created even with no sources (empty lists)."""
        result = import_docs(working_dir=str(tmp_path))
        assert Path(result["output_dir"]).is_dir()


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------

class TestImportDocsCLI:
    def test_no_sources_exits_with_error(self):
        runner = CliRunner()
        result = runner.invoke(main, ["import-docs"])
        assert result.exit_code != 0
        assert "at least one" in result.output or "at least one" in (result.stderr_bytes or b"").decode("utf-8", errors="replace")

    @patch("repoforge.import_docs.fetch_npm_readme", return_value="# React\n\nUI lib")
    def test_npm_success(self, mock_fetch, tmp_path):
        runner = CliRunner()
        result = runner.invoke(main, [
            "import-docs",
            "-w", str(tmp_path),
            "--npm", "react",
        ])
        assert result.exit_code == 0
        out_file = tmp_path / ".repoforge" / "external-docs" / "npm--react.md"
        assert out_file.exists()

    @patch("repoforge.import_docs.fetch_npm_readme", side_effect=RuntimeError("fail"))
    def test_all_failed_exits_1(self, mock_fetch, tmp_path):
        runner = CliRunner()
        result = runner.invoke(main, [
            "import-docs",
            "-w", str(tmp_path),
            "--npm", "bad-pkg",
        ])
        assert result.exit_code == 1

    @patch("repoforge.import_docs.fetch_npm_readme", return_value="# A")
    def test_quiet_mode(self, mock_fetch, tmp_path):
        runner = CliRunner()
        result = runner.invoke(main, [
            "import-docs",
            "-w", str(tmp_path),
            "--npm", "react",
            "-q",
        ])
        assert result.exit_code == 0
