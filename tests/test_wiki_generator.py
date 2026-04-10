"""Tests for wiki_generator — topic-based documentation generation."""

import tempfile
from pathlib import Path

from repoforge.wiki_generator import (
    Wiki,
    WikiArticle,
    build_wiki,
    classify_files,
    detect_topic,
    render_article,
    render_index,
    write_wiki,
)


class TestDetectTopic:
    def test_detects_auth(self):
        assert detect_topic("src/auth/login.ts") == "auth"

    def test_detects_database(self):
        assert detect_topic("src/models/user.py") == "database"

    def test_detects_api(self):
        assert detect_topic("src/routes/api.ts") == "api"

    def test_detects_testing(self):
        assert detect_topic("tests/test_utils.py") == "testing"

    def test_returns_none_for_unknown(self):
        assert detect_topic("README.md") is None


class TestClassifyFiles:
    def test_groups_by_topic(self):
        files = [
            "src/auth/login.ts",
            "src/auth/jwt.ts",
            "src/db/connection.ts",
            "src/routes/users.ts",
            "tests/test_utils.ts",
        ]
        groups = classify_files(files)
        assert "auth" in groups
        assert len(groups["auth"]) == 2
        assert "database" in groups
        assert "api" in groups
        assert "testing" in groups


class TestBuildWiki:
    def test_builds_from_files(self):
        files = [
            "src/auth/login.ts",
            "src/auth/middleware.ts",
            "src/db/models.ts",
            "src/routes/api.ts",
        ]
        wiki = build_wiki(files, "my-app")
        assert wiki.article_count() >= 2
        assert wiki.project_name == "my-app"

    def test_includes_file_listing(self):
        files = ["src/auth/login.ts", "src/auth/jwt.ts"]
        wiki = build_wiki(files)
        article = wiki.get_article("auth")
        assert article is not None
        assert any("login.ts" in s for s in article.sections)

    def test_includes_decisions(self):
        files = ["src/auth/login.ts"]
        decisions = [
            {"marker": "WHY", "text": "JWT over sessions", "file": "src/auth/login.ts"},
        ]
        wiki = build_wiki(files, decisions=decisions)
        article = wiki.get_article("auth")
        assert article is not None
        assert any("JWT" in s for s in article.sections)

    def test_finds_related_topics(self):
        files = [
            "src/auth/login.ts",
            "src/db/models.ts",
            "src/routes/api.ts",
        ]
        wiki = build_wiki(files)
        auth = wiki.get_article("auth")
        assert auth is not None
        assert len(auth.related) > 0

    def test_empty_files(self):
        wiki = build_wiki([])
        assert wiki.article_count() == 0


class TestRendering:
    def test_render_article(self):
        article = WikiArticle(
            slug="auth",
            title="Authentication",
            sections=["## Overview\n\nAuth stuff.\n"],
            related=["database"],
            files=["src/auth.ts"],
        )
        md = render_article(article)
        assert "# Authentication" in md
        assert "Auth stuff" in md
        assert "[database]" in md

    def test_render_index(self):
        wiki = Wiki(project_name="test-app")
        wiki.add_article(WikiArticle(slug="auth", title="Auth", files=["a.ts"]))
        wiki.add_article(WikiArticle(slug="db", title="Database", files=["b.ts", "c.ts"]))

        md = render_index(wiki)
        assert "test-app Wiki" in md
        assert "[Auth]" in md
        assert "(2 files)" in md


class TestWriteWiki:
    def test_writes_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki = build_wiki(
                ["src/auth/login.ts", "src/db/models.ts"],
                "my-project",
            )
            written = write_wiki(wiki, Path(tmpdir) / "wiki")

            assert len(written) >= 2  # index + at least 1 article
            assert (Path(tmpdir) / "wiki" / "index.md").exists()

    def test_articles_are_valid_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki = build_wiki(["src/auth/login.ts"], "test")
            write_wiki(wiki, Path(tmpdir) / "wiki")

            auth_path = Path(tmpdir) / "wiki" / "auth.md"
            if auth_path.exists():
                content = auth_path.read_text()
                assert content.startswith("# ")
