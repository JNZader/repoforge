"""Output format renderers for generated documentation.

Each renderer takes a list of chapter dicts and project metadata,
and produces a dict of filename → content. The write() method
persists the files to disk.

Available renderers:
- markdown: Individual .md files (default, passthrough)
- llms-txt: llms.txt + llms-full.txt for AI consumption (844K+ sites standard)
- json: Single docs.json with structured metadata + content

Usage:
    from repoforge.renderers import get_renderer
    renderer = get_renderer("llms-txt")
    files = renderer.render(chapters, metadata)
    renderer.write(files, output_dir)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RendererProtocol:
    """Base class for all renderers."""

    name: str = ""

    def render(self, chapters: list[dict], meta: dict) -> dict[str, str]:
        """Render chapters into a dict of filename → content.

        Args:
            chapters: List of {"file": str, "title": str, "content": str}
            meta: {"project_name": str, "language": str, "url": str, ...}

        Returns:
            Dict mapping output filenames to their string content.
        """
        raise NotImplementedError

    def write(self, files: dict[str, str], output_dir: Path) -> list[str]:
        """Write rendered files to disk. Returns list of created file paths."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        created = []
        for filename, content in files.items():
            path = output_dir / filename
            path.write_text(content, encoding="utf-8")
            created.append(str(path))
        return created


class MarkdownRenderer(RendererProtocol):
    """Passthrough renderer — outputs individual .md files as-is."""

    name = "markdown"

    def render(self, chapters: list[dict], meta: dict) -> dict[str, str]:
        return {ch["file"]: ch["content"] for ch in chapters}


class LlmsTxtRenderer(RendererProtocol):
    """Renders llms.txt (summary) + llms-full.txt (complete content).

    llms.txt is the emerging standard for AI-consumable site maps.
    See: https://llmstxt.org/
    """

    name = "llms-txt"

    def render(self, chapters: list[dict], meta: dict) -> dict[str, str]:
        project = meta.get("project_name", "Project")
        url = meta.get("url", "")

        # llms.txt — summary with chapter titles and descriptions
        summary_lines = [
            f"# {project}",
            "",
            f"> Documentation for {project}",
            "",
        ]
        if url:
            summary_lines.append(f"Source: {url}")
            summary_lines.append("")

        summary_lines.append("## Chapters")
        summary_lines.append("")
        for ch in chapters:
            # Extract first paragraph as description
            content = ch["content"]
            paragraphs = [p.strip() for p in content.split("\n\n") if p.strip() and not p.strip().startswith("#")]
            desc = paragraphs[0][:150] if paragraphs else ch.get("title", "")
            summary_lines.append(f"- [{ch['title']}]({ch['file']}): {desc}")

        # llms-full.txt — all content concatenated with section markers
        full_lines = [
            f"# {project} — Full Documentation",
            "",
        ]
        for ch in chapters:
            full_lines.append(f"---")
            full_lines.append(f"## {ch['title']}")
            full_lines.append(f"<!-- source: {ch['file']} -->")
            full_lines.append("")
            full_lines.append(ch["content"])
            full_lines.append("")

        return {
            "llms.txt": "\n".join(summary_lines),
            "llms-full.txt": "\n".join(full_lines),
        }


class JsonRenderer(RendererProtocol):
    """Renders a single JSON file with structured metadata + content."""

    name = "json"

    def render(self, chapters: list[dict], meta: dict) -> dict[str, str]:
        data = {
            "project_name": meta.get("project_name", ""),
            "language": meta.get("language", "English"),
            "url": meta.get("url", ""),
            "chapters": [
                {
                    "file": ch["file"],
                    "title": ch["title"],
                    "content": ch["content"],
                }
                for ch in chapters
            ],
        }
        return {"docs.json": json.dumps(data, indent=2, ensure_ascii=False)}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_RENDERERS = {
    "markdown": MarkdownRenderer,
    "llms-txt": LlmsTxtRenderer,
    "json": JsonRenderer,
}


def get_renderer(name: str) -> RendererProtocol:
    """Get a renderer by name. Raises ValueError for unknown renderers."""
    cls = _RENDERERS.get(name)
    if cls is None:
        available = ", ".join(sorted(_RENDERERS.keys()))
        raise ValueError(f"Unknown renderer '{name}'. Available: {available}")
    return cls()
