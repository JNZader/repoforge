"""Tests for Wave 8: Output format renderers."""

import json
from pathlib import Path

import pytest

from repoforge.renderers import (
    JsonRenderer,
    LlmsTxtRenderer,
    MarkdownRenderer,
    RendererProtocol,
    get_renderer,
)

SAMPLE_CHAPTERS = [
    {"file": "01-overview.md", "title": "Overview", "content": "# Overview\n\nProject overview."},
    {"file": "02-quickstart.md", "title": "Quick Start", "content": "# Quick Start\n\nHow to start."},
    {"file": "03-architecture.md", "title": "Architecture", "content": "# Architecture\n\nSystem design."},
]

PROJECT_META = {
    "project_name": "TestProject",
    "language": "English",
    "url": "https://github.com/test/project",
}


# ── get_renderer factory ─────────────────────────────────────────────────


class TestGetRenderer:

    def test_markdown(self):
        r = get_renderer("markdown")
        assert isinstance(r, MarkdownRenderer)

    def test_llms_txt(self):
        r = get_renderer("llms-txt")
        assert isinstance(r, LlmsTxtRenderer)

    def test_json(self):
        r = get_renderer("json")
        assert isinstance(r, JsonRenderer)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown renderer"):
            get_renderer("pdf")

    def test_all_implement_protocol(self):
        for name in ("markdown", "llms-txt", "json"):
            r = get_renderer(name)
            assert isinstance(r, RendererProtocol)


# ── MarkdownRenderer ─────────────────────────────────────────────────────


class TestMarkdownRenderer:

    def test_render_returns_dict_of_files(self):
        r = MarkdownRenderer()
        files = r.render(SAMPLE_CHAPTERS, PROJECT_META)
        assert isinstance(files, dict)
        assert "01-overview.md" in files

    def test_content_preserved(self):
        r = MarkdownRenderer()
        files = r.render(SAMPLE_CHAPTERS, PROJECT_META)
        assert files["01-overview.md"] == "# Overview\n\nProject overview."

    def test_write_to_disk(self, tmp_path):
        r = MarkdownRenderer()
        files = r.render(SAMPLE_CHAPTERS, PROJECT_META)
        r.write(files, tmp_path)
        assert (tmp_path / "01-overview.md").exists()
        assert "Overview" in (tmp_path / "01-overview.md").read_text()


# ── LlmsTxtRenderer ─────────────────────────────────────────────────────


class TestLlmsTxtRenderer:

    def test_render_returns_single_file(self):
        r = LlmsTxtRenderer()
        files = r.render(SAMPLE_CHAPTERS, PROJECT_META)
        assert "llms.txt" in files

    def test_contains_project_name(self):
        r = LlmsTxtRenderer()
        files = r.render(SAMPLE_CHAPTERS, PROJECT_META)
        assert "TestProject" in files["llms.txt"]

    def test_contains_all_chapter_content(self):
        r = LlmsTxtRenderer()
        files = r.render(SAMPLE_CHAPTERS, PROJECT_META)
        txt = files["llms.txt"]
        assert "Overview" in txt
        assert "Quick Start" in txt
        assert "Architecture" in txt

    def test_sections_separated(self):
        r = LlmsTxtRenderer()
        files = r.render(SAMPLE_CHAPTERS, PROJECT_META)
        # llms.txt uses section markers
        assert "---" in files["llms.txt"] or "##" in files["llms.txt"]

    def test_also_generates_llms_full(self):
        r = LlmsTxtRenderer()
        files = r.render(SAMPLE_CHAPTERS, PROJECT_META)
        assert "llms-full.txt" in files
        # Full version has all content
        assert len(files["llms-full.txt"]) >= len(files["llms.txt"])

    def test_write_to_disk(self, tmp_path):
        r = LlmsTxtRenderer()
        files = r.render(SAMPLE_CHAPTERS, PROJECT_META)
        r.write(files, tmp_path)
        assert (tmp_path / "llms.txt").exists()
        assert (tmp_path / "llms-full.txt").exists()


# ── JsonRenderer ─────────────────────────────────────────────────────────


class TestJsonRenderer:

    def test_render_returns_single_file(self):
        r = JsonRenderer()
        files = r.render(SAMPLE_CHAPTERS, PROJECT_META)
        assert "docs.json" in files

    def test_valid_json(self):
        r = JsonRenderer()
        files = r.render(SAMPLE_CHAPTERS, PROJECT_META)
        data = json.loads(files["docs.json"])
        assert isinstance(data, dict)

    def test_contains_metadata(self):
        r = JsonRenderer()
        files = r.render(SAMPLE_CHAPTERS, PROJECT_META)
        data = json.loads(files["docs.json"])
        assert data["project_name"] == "TestProject"

    def test_contains_chapters(self):
        r = JsonRenderer()
        files = r.render(SAMPLE_CHAPTERS, PROJECT_META)
        data = json.loads(files["docs.json"])
        assert len(data["chapters"]) == 3
        assert data["chapters"][0]["title"] == "Overview"
        assert data["chapters"][0]["content"] == "# Overview\n\nProject overview."

    def test_write_to_disk(self, tmp_path):
        r = JsonRenderer()
        files = r.render(SAMPLE_CHAPTERS, PROJECT_META)
        r.write(files, tmp_path)
        assert (tmp_path / "docs.json").exists()
        data = json.loads((tmp_path / "docs.json").read_text())
        assert data["project_name"] == "TestProject"
