"""Tests for skills_from_docs.ingest module."""

import pytest
from pathlib import Path

from repoforge.skills_from_docs.ingest import (
    detect_source_type,
    read_local_dir,
    ingest,
)
from repoforge.skills_from_docs.types import SourceType


class TestDetectSourceType:
    def test_github_repo_url(self):
        assert detect_source_type("https://github.com/org/repo") == SourceType.GITHUB_REPO

    def test_github_repo_url_with_git_suffix(self):
        assert detect_source_type("https://github.com/org/repo.git") == SourceType.GITHUB_REPO

    def test_github_repo_trailing_slash(self):
        assert detect_source_type("https://github.com/org/repo/") == SourceType.GITHUB_REPO

    def test_generic_url(self):
        assert detect_source_type("https://docs.example.com/guide") == SourceType.URL

    def test_http_url(self):
        assert detect_source_type("http://example.com/docs") == SourceType.URL

    def test_local_dir(self, tmp_path):
        assert detect_source_type(str(tmp_path)) == SourceType.LOCAL_DIR

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Cannot determine source type"):
            detect_source_type("/nonexistent/path/nowhere")


class TestReadLocalDir:
    def test_reads_markdown_files(self, tmp_path):
        (tmp_path / "README.md").write_text("# Hello\nWorld")
        (tmp_path / "guide.md").write_text("# Guide\nContent here")
        result = read_local_dir(str(tmp_path))
        assert len(result) == 2
        assert any("Hello" in r for r in result)
        assert any("Guide" in r for r in result)

    def test_reads_nested_files(self, tmp_path):
        sub = tmp_path / "docs" / "api"
        sub.mkdir(parents=True)
        (sub / "reference.md").write_text("# API Reference")
        result = read_local_dir(str(tmp_path))
        assert len(result) == 1
        assert "API Reference" in result[0]

    def test_skips_git_dir(self, tmp_path):
        git = tmp_path / ".git"
        git.mkdir()
        (git / "config.md").write_text("git internals")
        (tmp_path / "README.md").write_text("# Real file")
        result = read_local_dir(str(tmp_path))
        assert len(result) == 1
        assert "Real file" in result[0]

    def test_skips_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "README.md").write_text("package readme")
        (tmp_path / "docs.md").write_text("# Docs")
        result = read_local_dir(str(tmp_path))
        assert len(result) == 1

    def test_empty_dir_raises(self, tmp_path):
        with pytest.raises(RuntimeError, match="No documentation files found"):
            read_local_dir(str(tmp_path))

    def test_nonexistent_dir_raises(self):
        with pytest.raises(RuntimeError, match="does not exist"):
            read_local_dir("/nonexistent/dir")

    def test_reads_html_files(self, tmp_path):
        (tmp_path / "index.html").write_text("<h1>Title</h1><p>Content</p>")
        result = read_local_dir(str(tmp_path))
        assert len(result) == 1
        assert "Title" in result[0]


class TestIngest:
    def test_local_dir_dispatch(self, tmp_path):
        (tmp_path / "README.md").write_text("# Test\nContent")
        result = ingest(str(tmp_path))
        assert len(result) >= 1
        assert "Test" in result[0]

    def test_invalid_source(self):
        with pytest.raises(ValueError):
            ingest("/nonexistent/path/12345")
