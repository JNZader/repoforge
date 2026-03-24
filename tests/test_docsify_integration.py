"""
tests/test_docsify_integration.py — Integration tests for Docsify site generation.

Exercises build_docsify_files with real temp directories and verifies
the generated file structure, content, and HTML validity.
"""

from pathlib import Path

import pytest

from repoforge.docsify import (
    build_docsify_files,
    _build_sidebar,
    _build_index_html,
    _theme_url,
    _language_to_code,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def output_dir(tmp_path):
    """Pre-created output directory."""
    d = tmp_path / "docs"
    d.mkdir()
    return d


@pytest.fixture
def flat_chapters():
    """Chapters for a single-project layout."""
    return [
        {"file": "index.md", "title": "Home", "description": "Project overview"},
        {"file": "01-overview.md", "title": "Overview", "description": "Tech stack"},
        {"file": "02-quickstart.md", "title": "Quick Start", "description": "Getting started"},
        {"file": "03-architecture.md", "title": "Architecture", "description": "Design"},
    ]


@pytest.fixture
def monorepo_chapters():
    """Chapters for a monorepo layout with subdirs."""
    return [
        {"file": "index.md", "title": "Home", "description": "Root overview"},
        {"file": "03-architecture.md", "title": "Architecture", "description": "Overall design"},
        {
            "file": "index.md", "title": "Frontend Layer",
            "description": "Frontend docs", "subdir": "frontend",
            "project_type": "web_app",
        },
        {
            "file": "05-components.md", "title": "Components",
            "description": "UI components", "subdir": "frontend",
            "project_type": "web_app",
        },
        {
            "file": "index.md", "title": "Backend Layer",
            "description": "Backend docs", "subdir": "backend",
            "project_type": "api_service",
        },
        {
            "file": "06-api-reference.md", "title": "API Reference",
            "description": "Endpoints", "subdir": "backend",
            "project_type": "api_service",
        },
    ]


# ---------------------------------------------------------------------------
# build_docsify_files — full pipeline
# ---------------------------------------------------------------------------

class TestBuildDocsifyFiles:
    def test_creates_three_files(self, output_dir, flat_chapters):
        files = build_docsify_files(
            output_dir=output_dir,
            project_name="Test Project",
            chapters=flat_chapters,
        )
        assert len(files) == 3
        assert (output_dir / "_sidebar.md").exists()
        assert (output_dir / ".nojekyll").exists()
        assert (output_dir / "index.html").exists()

    def test_returns_absolute_paths(self, output_dir, flat_chapters):
        files = build_docsify_files(
            output_dir=output_dir,
            project_name="Test",
            chapters=flat_chapters,
        )
        for f in files:
            assert Path(f).is_absolute()

    def test_nojekyll_is_empty(self, output_dir, flat_chapters):
        build_docsify_files(
            output_dir=output_dir,
            project_name="Test",
            chapters=flat_chapters,
        )
        content = (output_dir / ".nojekyll").read_text()
        assert content == ""

    def test_index_html_contains_project_name(self, output_dir, flat_chapters):
        build_docsify_files(
            output_dir=output_dir,
            project_name="My Cool Project",
            chapters=flat_chapters,
        )
        html = (output_dir / "index.html").read_text()
        assert "My Cool Project" in html

    def test_sidebar_contains_chapters(self, output_dir, flat_chapters):
        build_docsify_files(
            output_dir=output_dir,
            project_name="Test",
            chapters=flat_chapters,
        )
        sidebar = (output_dir / "_sidebar.md").read_text()
        assert "Home" in sidebar
        assert "Overview" in sidebar
        assert "Architecture" in sidebar

    def test_with_custom_theme(self, output_dir, flat_chapters):
        build_docsify_files(
            output_dir=output_dir,
            project_name="Test",
            chapters=flat_chapters,
            theme="dark",
        )
        html = (output_dir / "index.html").read_text()
        assert "dark.css" in html

    def test_with_custom_language(self, output_dir, flat_chapters):
        build_docsify_files(
            output_dir=output_dir,
            project_name="Test",
            chapters=flat_chapters,
            language="Spanish",
        )
        html = (output_dir / "index.html").read_text()
        assert 'lang="es"' in html

    def test_empty_chapters(self, output_dir):
        files = build_docsify_files(
            output_dir=output_dir,
            project_name="Empty",
            chapters=[],
        )
        assert len(files) == 3
        html = (output_dir / "index.html").read_text()
        assert "README.md" in html  # fallback homepage

    def test_monorepo_layout(self, output_dir, monorepo_chapters):
        build_docsify_files(
            output_dir=output_dir,
            project_name="MonoProject",
            chapters=monorepo_chapters,
        )
        sidebar = (output_dir / "_sidebar.md").read_text()
        assert "Frontend" in sidebar
        assert "Backend" in sidebar
        assert "frontend/" in sidebar
        assert "backend/" in sidebar


# ---------------------------------------------------------------------------
# _build_sidebar
# ---------------------------------------------------------------------------

class TestBuildSidebar:
    def test_flat_sidebar(self, flat_chapters):
        sidebar = _build_sidebar("Test", flat_chapters)
        assert "**Test**" in sidebar
        assert "[Home](index)" in sidebar
        assert "[Overview](01-overview)" in sidebar
        # .md should be stripped from links
        assert ".md" not in sidebar

    def test_hierarchical_sidebar(self, monorepo_chapters):
        sidebar = _build_sidebar("Mono", monorepo_chapters)
        assert "**Mono**" in sidebar
        assert "**Frontend" in sidebar
        assert "**Backend" in sidebar
        assert "frontend/index" in sidebar
        assert "backend/06-api-reference" in sidebar

    def test_empty_chapters(self):
        sidebar = _build_sidebar("Empty", [])
        assert "**Empty**" in sidebar

    def test_single_chapter(self):
        chapters = [{"file": "index.md", "title": "Home", "description": "Main"}]
        sidebar = _build_sidebar("Single", chapters)
        assert "[Home](index)" in sidebar


# ---------------------------------------------------------------------------
# _build_index_html
# ---------------------------------------------------------------------------

class TestBuildIndexHtml:
    def test_valid_html_structure(self):
        html = _build_index_html("Test", "en", "vue", "index.md")
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html

    def test_project_name_in_title(self):
        html = _build_index_html("My Project", "en", "vue", "index.md")
        assert "<title>My Project</title>" in html

    def test_lang_attribute(self):
        html = _build_index_html("Test", "es", "vue", "index.md")
        assert 'lang="es"' in html

    def test_homepage_config(self):
        html = _build_index_html("Test", "en", "vue", "01-overview.md")
        assert "01-overview.md" in html

    def test_docsify_script_included(self):
        html = _build_index_html("Test", "en", "vue", "index.md")
        assert "docsify" in html
        assert "docsify.min.js" in html

    def test_mermaid_support(self):
        html = _build_index_html("Test", "en", "vue", "index.md")
        assert "mermaid" in html

    def test_search_plugin(self):
        html = _build_index_html("Test", "en", "vue", "index.md")
        assert "search" in html

    def test_escapes_quotes_in_name(self):
        html = _build_index_html("It's a \"test\"", "en", "vue", "index.md")
        assert "\\'" in html or "&quot;" in html

    def test_theme_css_link(self):
        html = _build_index_html("Test", "en", "dark", "index.md")
        assert "dark.css" in html


# ---------------------------------------------------------------------------
# _theme_url
# ---------------------------------------------------------------------------

class TestThemeUrl:
    def test_vue_theme(self):
        assert "vue.css" in _theme_url("vue")

    def test_dark_theme(self):
        assert "dark.css" in _theme_url("dark")

    def test_buble_theme(self):
        assert "buble.css" in _theme_url("buble")

    def test_pure_theme(self):
        assert "pure.css" in _theme_url("pure")

    def test_unknown_defaults_to_vue(self):
        assert "vue.css" in _theme_url("nonexistent")


# ---------------------------------------------------------------------------
# _language_to_code
# ---------------------------------------------------------------------------

class TestLanguageToCode:
    @pytest.mark.parametrize("lang,code", [
        ("English", "en"),
        ("Spanish", "es"),
        ("French", "fr"),
        ("German", "de"),
        ("Portuguese", "pt"),
        ("Chinese", "zh"),
        ("Japanese", "ja"),
        ("Korean", "ko"),
        ("Russian", "ru"),
        ("Italian", "it"),
        ("Dutch", "nl"),
    ])
    def test_supported_languages(self, lang, code):
        assert _language_to_code(lang) == code

    def test_case_insensitive(self):
        assert _language_to_code("ENGLISH") == "en"
        assert _language_to_code("spanish") == "es"

    def test_unknown_defaults_to_en(self):
        assert _language_to_code("Klingon") == "en"
