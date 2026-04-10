"""Declarative YAML page templates — control sections within generated doc pages.

While ``template_loader.py`` defines *which chapters* (files) are generated,
page templates define *which sections* appear inside each page, their order,
and any custom intro/outro text.

Users declare page templates in ``repoforge.yaml`` under the ``pages:`` key
or in standalone YAML files referenced by ``pages.path:``.

Example (in repoforge.yaml):

    pages:
      - file: "03-architecture.md"
        sections:
          - type: intro
            content: "This project follows a hexagonal architecture."
          - type: call_graph
            enabled: true
          - type: entity_diff
            enabled: false
          - type: diagram
            enabled: true
          - type: custom
            title: "Deployment Notes"
            content: "We deploy via GitHub Actions to ECS."

Available section types:
  - intro: Custom introductory text (rendered before generated content)
  - outro: Custom closing text (rendered after generated content)
  - call_graph: Dependency/call graph section
  - entity_diff: Entity-level diff section
  - diagram: Architecture diagrams (Mermaid)
  - data_models: Data model documentation
  - api_surface: API endpoints and surface area
  - custom: Arbitrary titled section with user-provided content
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PageTemplateError(Exception):
    """Raised when page template YAML is invalid."""


# ---------------------------------------------------------------------------
# Section types
# ---------------------------------------------------------------------------

VALID_SECTION_TYPES = frozenset({
    "intro",
    "outro",
    "call_graph",
    "entity_diff",
    "diagram",
    "data_models",
    "api_surface",
    "custom",
})


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SectionDef:
    """A single section within a page template."""

    type: str
    """Section type — must be one of VALID_SECTION_TYPES."""

    enabled: bool = True
    """Whether this section should be included in output."""

    title: str | None = None
    """Custom title (required for 'custom' type, optional otherwise)."""

    content: str | None = None
    """User-provided content (for 'intro', 'outro', 'custom' types)."""

    order: int = 0
    """Sort order within the page (lower = earlier)."""


@dataclass(frozen=True, slots=True)
class PageTemplate:
    """A page template controlling sections for a specific doc file."""

    file: str
    """Target chapter filename (e.g. '03-architecture.md')."""

    sections: tuple[SectionDef, ...] = field(default_factory=tuple)
    """Ordered list of section definitions."""

    @property
    def enabled_sections(self) -> list[SectionDef]:
        """Return only enabled sections, sorted by order."""
        return sorted(
            [s for s in self.sections if s.enabled],
            key=lambda s: s.order,
        )

    @property
    def disabled_section_types(self) -> set[str]:
        """Return set of section types explicitly disabled."""
        return {s.type for s in self.sections if not s.enabled}


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_page_templates(config: dict) -> dict[str, PageTemplate]:
    """Load page templates from repoforge config dict.

    Args:
        config: The ``repoforge_config`` dict (from ``repoforge.yaml``).

    Returns:
        Mapping of chapter filename to PageTemplate.
    """
    pages_raw = config.get("pages")
    if not pages_raw:
        return {}

    # Pages can be a list (inline) or a dict with 'path' key
    if isinstance(pages_raw, dict):
        path_str = pages_raw.get("path")
        if path_str:
            return _load_from_file(Path(path_str))
        items = pages_raw.get("items", [])
    elif isinstance(pages_raw, list):
        items = pages_raw
    else:
        msg = f"'pages' must be a list or dict, got {type(pages_raw).__name__}"
        raise PageTemplateError(msg)

    return _parse_page_list(items)


def _load_from_file(path: Path) -> dict[str, PageTemplate]:
    """Load page templates from a standalone YAML file."""
    if not path.exists():
        logger.warning("Page template file not found: %s", path)
        return {}

    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        msg = f"{path}: page template file must be a YAML mapping"
        raise PageTemplateError(msg)

    items = raw.get("pages", [])
    if not isinstance(items, list):
        msg = f"{path}: 'pages' must be a list"
        raise PageTemplateError(msg)

    return _parse_page_list(items, source=str(path))


def _parse_page_list(
    items: list[Any],
    source: str = "repoforge.yaml",
) -> dict[str, PageTemplate]:
    """Parse a list of raw page dicts into PageTemplate objects."""
    templates: dict[str, PageTemplate] = {}

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            msg = f"{source}: page #{i} must be a mapping"
            raise PageTemplateError(msg)

        file_name = item.get("file")
        if not file_name:
            msg = f"{source}: page #{i} missing required 'file' field"
            raise PageTemplateError(msg)

        sections_raw = item.get("sections", [])
        if not isinstance(sections_raw, list):
            msg = f"{source}: page '{file_name}' sections must be a list"
            raise PageTemplateError(msg)

        sections: list[SectionDef] = []
        for j, sec_raw in enumerate(sections_raw):
            if not isinstance(sec_raw, dict):
                msg = f"{source}: page '{file_name}' section #{j} must be a mapping"
                raise PageTemplateError(msg)

            sec_type = sec_raw.get("type")
            if not sec_type:
                msg = f"{source}: page '{file_name}' section #{j} missing 'type'"
                raise PageTemplateError(msg)

            if sec_type not in VALID_SECTION_TYPES:
                msg = (
                    f"{source}: page '{file_name}' section #{j} has invalid "
                    f"type '{sec_type}'. Valid: {sorted(VALID_SECTION_TYPES)}"
                )
                raise PageTemplateError(msg)

            # 'custom' type requires title
            if sec_type == "custom" and not sec_raw.get("title"):
                msg = (
                    f"{source}: page '{file_name}' section #{j} "
                    f"of type 'custom' requires a 'title'"
                )
                raise PageTemplateError(msg)

            sections.append(SectionDef(
                type=sec_type,
                enabled=bool(sec_raw.get("enabled", True)),
                title=sec_raw.get("title"),
                content=sec_raw.get("content"),
                order=int(sec_raw.get("order", j)),
            ))

        templates[str(file_name)] = PageTemplate(
            file=str(file_name),
            sections=tuple(sections),
        )

    return templates


# ---------------------------------------------------------------------------
# Section rendering
# ---------------------------------------------------------------------------


def render_page_sections(
    page_template: PageTemplate,
    generated_content: str,
    context: dict[str, str] | None = None,
) -> str:
    """Render a page by assembling sections around generated content.

    The generated LLM content is placed in the middle. Intro sections go
    before, outro sections after. Disabled section types are stripped from
    the generated content if they appear as markdown headings.

    Args:
        page_template: The page template with section definitions.
        generated_content: The LLM-generated markdown content for this page.
        context: Optional context dict with keys like 'call_graph', 'diagram',
            'entity_diff' etc. for injecting pre-built content blocks.

    Returns:
        Final assembled markdown content.
    """
    context = context or {}
    sections = page_template.enabled_sections
    disabled = page_template.disabled_section_types

    parts: list[str] = []

    # 1. Render intro sections first
    for sec in sections:
        if sec.type == "intro" and sec.content:
            parts.append(sec.content.strip())
            parts.append("")

    # 2. Strip disabled section types from generated content
    content = _strip_disabled_sections(generated_content, disabled)

    # 3. Add the (possibly stripped) generated content
    parts.append(content.strip())

    # 4. Add custom sections inline
    for sec in sections:
        if sec.type == "custom" and sec.content:
            parts.append("")
            parts.append(f"## {sec.title}")
            parts.append("")
            parts.append(sec.content.strip())

    # 5. Render outro sections last
    for sec in sections:
        if sec.type == "outro" and sec.content:
            parts.append("")
            parts.append(sec.content.strip())

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Section-type to heading mapping (for stripping disabled sections)
# ---------------------------------------------------------------------------

_SECTION_HEADINGS: dict[str, list[str]] = {
    "call_graph": ["call graph", "dependency graph", "call tree"],
    "entity_diff": ["entity diff", "entity changes", "entity-level diff"],
    "diagram": ["diagram", "architecture diagram", "mermaid"],
    "data_models": ["data model", "data structure", "schema"],
    "api_surface": ["api reference", "api surface", "endpoint"],
}


def _strip_disabled_sections(content: str, disabled: set[str]) -> str:
    """Remove markdown sections whose type is in the disabled set.

    Looks for ## or ### headings that match known section-type keywords
    and removes everything from the heading to the next same-level heading.
    """
    if not disabled:
        return content

    # Build set of lowercase keywords to strip
    keywords: set[str] = set()
    for sec_type in disabled:
        for heading in _SECTION_HEADINGS.get(sec_type, []):
            keywords.add(heading.lower())

    if not keywords:
        return content

    lines = content.split("\n")
    result: list[str] = []
    skip_until_level: int | None = None

    for line in lines:
        stripped = line.strip()

        # Detect heading level
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            heading_text = stripped.lstrip("#").strip().lower()

            # Check if this heading matches a disabled section
            if any(kw in heading_text for kw in keywords):
                skip_until_level = level
                continue

            # If we were skipping, stop at same or higher level heading
            if skip_until_level is not None and level <= skip_until_level:
                skip_until_level = None

        if skip_until_level is not None:
            continue

        result.append(line)

    return "\n".join(result)
