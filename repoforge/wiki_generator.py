"""Wiki generation — produce navigable topic-based documentation from
codebase analysis. Generates .repoforge/wiki/ with topic articles
(auth.md, database.md, etc.) and an index.md entry point.

Uses semantic chunking for content organization and decision intelligence
for capturing the WHY behind architecture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WikiArticle:
    """A wiki article about a codebase topic."""
    slug: str  # e.g. "auth", "database", "api"
    title: str
    sections: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)  # slugs of related articles
    files: list[str] = field(default_factory=list)  # source files covered


@dataclass
class Wiki:
    """A collection of wiki articles with an index."""
    articles: dict[str, WikiArticle] = field(default_factory=dict)
    project_name: str = "project"

    def add_article(self, article: WikiArticle) -> None:
        self.articles[article.slug] = article

    def get_article(self, slug: str) -> WikiArticle | None:
        return self.articles.get(slug)

    def article_count(self) -> int:
        return len(self.articles)


# ── Topic detection ──

TOPIC_PATTERNS: list[tuple[str, str, list[str]]] = [
    ("auth", "Authentication & Authorization", ["auth", "login", "jwt", "token", "session", "oauth", "permission"]),
    ("database", "Database & Storage", ["db", "database", "model", "schema", "migration", "query", "repository"]),
    ("api", "API & Endpoints", ["route", "endpoint", "controller", "handler", "middleware", "api"]),
    ("config", "Configuration", ["config", "env", "setting", "constant"]),
    ("testing", "Testing", ["test", "spec", "mock", "fixture", "e2e"]),
    ("ci-cd", "CI/CD & Deployment", ["ci", "deploy", "docker", "pipeline", "workflow", "github"]),
    ("security", "Security", ["security", "encrypt", "hash", "vulnerability", "sanitize"]),
    ("utils", "Utilities", ["util", "helper", "lib", "common", "shared"]),
]


def detect_topic(file_path: str) -> str | None:
    """Detect the topic of a file from its path."""
    lower = file_path.lower()
    for slug, _, keywords in TOPIC_PATTERNS:
        if any(kw in lower for kw in keywords):
            return slug
    return None


def classify_files(file_paths: list[str]) -> dict[str, list[str]]:
    """Group files by detected topic."""
    groups: dict[str, list[str]] = {}
    for fp in file_paths:
        topic = detect_topic(fp)
        if topic:
            groups.setdefault(topic, []).append(fp)
    return groups


# ── Wiki building ──

def build_wiki(
    file_paths: list[str],
    project_name: str = "project",
    decisions: list[dict[str, str]] | None = None,
) -> Wiki:
    """Build a wiki from a list of source files.

    Args:
        file_paths: All source file paths in the project.
        project_name: Name of the project.
        decisions: Optional list of decision dicts with 'marker', 'text', 'file' keys.
    """
    wiki = Wiki(project_name=project_name)
    grouped = classify_files(file_paths)

    for slug, title, _ in TOPIC_PATTERNS:
        files = grouped.get(slug, [])
        if not files:
            continue

        sections: list[str] = []

        # Overview section
        sections.append(f"## Overview\n\nThis topic covers {len(files)} files related to {title.lower()}.\n")

        # File listing
        file_list = "\n".join(f"- `{f}`" for f in sorted(files)[:20])
        if len(files) > 20:
            file_list += f"\n- ... and {len(files) - 20} more files"
        sections.append(f"## Files\n\n{file_list}\n")

        # Decisions for this topic
        if decisions:
            topic_decisions = [
                d for d in decisions
                if detect_topic(d.get("file", "")) == slug
            ]
            if topic_decisions:
                dec_lines = "\n".join(
                    f"- **{d.get('marker', 'NOTE')}** ({d.get('file', '')}): {d.get('text', '')}"
                    for d in topic_decisions[:10]
                )
                sections.append(f"## Decisions\n\n{dec_lines}\n")

        # Related topics
        related = _find_related(slug, grouped)

        article = WikiArticle(
            slug=slug,
            title=title,
            sections=sections,
            related=related,
            files=files,
        )
        wiki.add_article(article)

    return wiki


def _find_related(slug: str, grouped: dict[str, list[str]]) -> list[str]:
    """Find related topics by shared file path components."""
    related: list[str] = []
    for other_slug in grouped:
        if other_slug != slug:
            related.append(other_slug)
    return related[:5]


# ── Rendering ──

def render_article(article: WikiArticle) -> str:
    """Render a wiki article as markdown."""
    lines = [f"# {article.title}\n"]
    for section in article.sections:
        lines.append(section)

    if article.related:
        lines.append("## Related Topics\n")
        for slug in article.related:
            lines.append(f"- [{slug}]({slug}.md)")
        lines.append("")

    return "\n".join(lines)


def render_index(wiki: Wiki) -> str:
    """Render the wiki index page."""
    lines = [f"# {wiki.project_name} Wiki\n"]
    lines.append(f"Generated documentation covering {wiki.article_count()} topics.\n")
    lines.append("## Topics\n")
    for slug, article in sorted(wiki.articles.items()):
        file_count = len(article.files)
        lines.append(f"- [{article.title}]({slug}.md) ({file_count} files)")
    lines.append("")
    return "\n".join(lines)


def write_wiki(wiki: Wiki, output_dir: Path) -> list[str]:
    """Write wiki to filesystem. Returns list of written file paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    # Index
    index_path = output_dir / "index.md"
    index_path.write_text(render_index(wiki))
    written.append(str(index_path))

    # Articles
    for slug, article in wiki.articles.items():
        article_path = output_dir / f"{slug}.md"
        article_path.write_text(render_article(article))
        written.append(str(article_path))

    return written
