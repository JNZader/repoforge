"""Tests for page templates — section-level control within generated doc pages.

Covers:
- PageTemplateError validation
- SectionDef and PageTemplate dataclasses
- load_page_templates (inline list, dict with path, standalone file)
- Section validation (valid types, custom requires title)
- render_page_sections (intro, outro, custom, disabled section stripping)
- _strip_disabled_sections (heading-based removal)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from repoforge.page_templates import (
    VALID_SECTION_TYPES,
    PageTemplate,
    PageTemplateError,
    SectionDef,
    _strip_disabled_sections,
    load_page_templates,
    render_page_sections,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _write_yaml(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(data, f)
    return path


# ══════════════════════════════════════════════════════════════════════════════
# SectionDef dataclass
# ══════════════════════════════════════════════════════════════════════════════


class TestSectionDef:
    def test_defaults(self):
        sec = SectionDef(type="intro")
        assert sec.enabled is True
        assert sec.title is None
        assert sec.content is None
        assert sec.order == 0

    def test_frozen(self):
        sec = SectionDef(type="intro")
        with pytest.raises(AttributeError):
            sec.type = "outro"  # type: ignore[misc]

    def test_all_fields(self):
        sec = SectionDef(
            type="custom",
            enabled=True,
            title="My Section",
            content="Some text",
            order=5,
        )
        assert sec.type == "custom"
        assert sec.title == "My Section"
        assert sec.content == "Some text"
        assert sec.order == 5


# ══════════════════════════════════════════════════════════════════════════════
# PageTemplate dataclass
# ══════════════════════════════════════════════════════════════════════════════


class TestPageTemplate:
    def test_enabled_sections_filters_disabled(self):
        sections = (
            SectionDef(type="intro", enabled=True, order=0),
            SectionDef(type="call_graph", enabled=False, order=1),
            SectionDef(type="outro", enabled=True, order=2),
        )
        pt = PageTemplate(file="test.md", sections=sections)
        enabled = pt.enabled_sections
        assert len(enabled) == 2
        assert enabled[0].type == "intro"
        assert enabled[1].type == "outro"

    def test_enabled_sections_sorted_by_order(self):
        sections = (
            SectionDef(type="outro", enabled=True, order=10),
            SectionDef(type="intro", enabled=True, order=1),
        )
        pt = PageTemplate(file="test.md", sections=sections)
        enabled = pt.enabled_sections
        assert enabled[0].type == "intro"
        assert enabled[1].type == "outro"

    def test_disabled_section_types(self):
        sections = (
            SectionDef(type="call_graph", enabled=False),
            SectionDef(type="entity_diff", enabled=False),
            SectionDef(type="intro", enabled=True),
        )
        pt = PageTemplate(file="test.md", sections=sections)
        assert pt.disabled_section_types == {"call_graph", "entity_diff"}

    def test_empty_sections(self):
        pt = PageTemplate(file="test.md")
        assert pt.enabled_sections == []
        assert pt.disabled_section_types == set()

    def test_frozen(self):
        pt = PageTemplate(file="test.md")
        with pytest.raises(AttributeError):
            pt.file = "other.md"  # type: ignore[misc]


# ══════════════════════════════════════════════════════════════════════════════
# load_page_templates
# ══════════════════════════════════════════════════════════════════════════════


class TestLoadPageTemplates:
    def test_empty_config(self):
        assert load_page_templates({}) == {}

    def test_no_pages_key(self):
        assert load_page_templates({"language": "English"}) == {}

    def test_inline_list(self):
        config = {
            "pages": [
                {
                    "file": "03-architecture.md",
                    "sections": [
                        {"type": "intro", "content": "Custom intro."},
                        {"type": "call_graph", "enabled": True},
                    ],
                },
            ],
        }
        result = load_page_templates(config)
        assert "03-architecture.md" in result
        pt = result["03-architecture.md"]
        assert len(pt.sections) == 2
        assert pt.sections[0].type == "intro"
        assert pt.sections[0].content == "Custom intro."

    def test_dict_with_items(self):
        config = {
            "pages": {
                "items": [
                    {
                        "file": "01-overview.md",
                        "sections": [{"type": "diagram", "enabled": False}],
                    },
                ],
            },
        }
        result = load_page_templates(config)
        assert "01-overview.md" in result
        assert result["01-overview.md"].sections[0].enabled is False

    def test_dict_with_path(self, tmp_path: Path):
        yaml_file = tmp_path / "pages.yaml"
        _write_yaml(yaml_file, {
            "pages": [
                {
                    "file": "07-dev-guide.md",
                    "sections": [{"type": "outro", "content": "Thanks!"}],
                },
            ],
        })
        config = {"pages": {"path": str(yaml_file)}}
        result = load_page_templates(config)
        assert "07-dev-guide.md" in result

    def test_path_not_found(self, tmp_path: Path):
        config = {"pages": {"path": str(tmp_path / "nonexistent.yaml")}}
        result = load_page_templates(config)
        assert result == {}

    def test_invalid_pages_type(self):
        with pytest.raises(PageTemplateError, match="must be a list or dict"):
            load_page_templates({"pages": "invalid"})

    def test_page_missing_file(self):
        config = {"pages": [{"sections": [{"type": "intro"}]}]}
        with pytest.raises(PageTemplateError, match="missing required 'file'"):
            load_page_templates(config)

    def test_section_missing_type(self):
        config = {
            "pages": [
                {"file": "test.md", "sections": [{"content": "hello"}]},
            ],
        }
        with pytest.raises(PageTemplateError, match="missing 'type'"):
            load_page_templates(config)

    def test_invalid_section_type(self):
        config = {
            "pages": [
                {"file": "test.md", "sections": [{"type": "nonexistent"}]},
            ],
        }
        with pytest.raises(PageTemplateError, match="invalid type 'nonexistent'"):
            load_page_templates(config)

    def test_custom_requires_title(self):
        config = {
            "pages": [
                {
                    "file": "test.md",
                    "sections": [{"type": "custom", "content": "no title"}],
                },
            ],
        }
        with pytest.raises(PageTemplateError, match="requires a 'title'"):
            load_page_templates(config)

    def test_custom_with_title_passes(self):
        config = {
            "pages": [
                {
                    "file": "test.md",
                    "sections": [
                        {"type": "custom", "title": "Notes", "content": "body"},
                    ],
                },
            ],
        }
        result = load_page_templates(config)
        assert result["test.md"].sections[0].title == "Notes"

    def test_multiple_pages(self):
        config = {
            "pages": [
                {"file": "a.md", "sections": [{"type": "intro", "content": "A"}]},
                {"file": "b.md", "sections": [{"type": "outro", "content": "B"}]},
            ],
        }
        result = load_page_templates(config)
        assert len(result) == 2
        assert "a.md" in result
        assert "b.md" in result

    def test_section_order_preserved(self):
        config = {
            "pages": [
                {
                    "file": "test.md",
                    "sections": [
                        {"type": "intro", "content": "first", "order": 10},
                        {"type": "outro", "content": "second", "order": 1},
                    ],
                },
            ],
        }
        result = load_page_templates(config)
        pt = result["test.md"]
        # Raw order is as declared
        assert pt.sections[0].order == 10
        assert pt.sections[1].order == 1
        # Enabled sections sorted by order
        enabled = pt.enabled_sections
        assert enabled[0].type == "outro"  # order=1
        assert enabled[1].type == "intro"  # order=10

    def test_sections_not_a_list(self):
        config = {
            "pages": [{"file": "test.md", "sections": "bad"}],
        }
        with pytest.raises(PageTemplateError, match="sections must be a list"):
            load_page_templates(config)

    def test_section_not_a_dict(self):
        config = {
            "pages": [{"file": "test.md", "sections": ["just a string"]}],
        }
        with pytest.raises(PageTemplateError, match="must be a mapping"):
            load_page_templates(config)

    def test_page_not_a_dict(self):
        config = {"pages": ["just a string"]}
        with pytest.raises(PageTemplateError, match="must be a mapping"):
            load_page_templates(config)


# ══════════════════════════════════════════════════════════════════════════════
# Standalone YAML file loading
# ══════════════════════════════════════════════════════════════════════════════


class TestLoadFromFile:
    def test_valid_file(self, tmp_path: Path):
        yaml_file = tmp_path / "pages.yaml"
        _write_yaml(yaml_file, {
            "pages": [
                {
                    "file": "03-architecture.md",
                    "sections": [
                        {"type": "intro", "content": "From file."},
                        {"type": "entity_diff", "enabled": False},
                    ],
                },
            ],
        })
        config = {"pages": {"path": str(yaml_file)}}
        result = load_page_templates(config)
        pt = result["03-architecture.md"]
        assert len(pt.sections) == 2
        assert pt.sections[1].enabled is False

    def test_non_dict_file_raises(self, tmp_path: Path):
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("- item1\n- item2\n")
        config = {"pages": {"path": str(yaml_file)}}
        with pytest.raises(PageTemplateError, match="must be a YAML mapping"):
            load_page_templates(config)

    def test_pages_not_list_in_file(self, tmp_path: Path):
        yaml_file = tmp_path / "bad.yaml"
        _write_yaml(yaml_file, {"pages": "not a list"})
        config = {"pages": {"path": str(yaml_file)}}
        with pytest.raises(PageTemplateError, match="must be a list"):
            load_page_templates(config)


# ══════════════════════════════════════════════════════════════════════════════
# render_page_sections
# ══════════════════════════════════════════════════════════════════════════════


class TestRenderPageSections:
    def test_no_sections_passthrough(self):
        pt = PageTemplate(file="test.md")
        content = "# Hello\n\nSome content."
        result = render_page_sections(pt, content)
        assert result == content

    def test_intro_prepended(self):
        sections = (SectionDef(type="intro", content="Welcome!", order=0),)
        pt = PageTemplate(file="test.md", sections=sections)
        result = render_page_sections(pt, "# Main\n\nBody.")
        assert result.startswith("Welcome!")
        assert "# Main" in result

    def test_outro_appended(self):
        sections = (SectionDef(type="outro", content="Goodbye!", order=0),)
        pt = PageTemplate(file="test.md", sections=sections)
        result = render_page_sections(pt, "# Main\n\nBody.")
        assert result.endswith("Goodbye!")

    def test_custom_section_added(self):
        sections = (
            SectionDef(
                type="custom",
                title="My Notes",
                content="Important notes here.",
                order=0,
            ),
        )
        pt = PageTemplate(file="test.md", sections=sections)
        result = render_page_sections(pt, "# Main\n\nBody.")
        assert "## My Notes" in result
        assert "Important notes here." in result

    def test_disabled_section_stripped(self):
        sections = (
            SectionDef(type="call_graph", enabled=False),
        )
        pt = PageTemplate(file="test.md", sections=sections)
        content = "# Main\n\nIntro.\n\n## Call Graph\n\nGraph content.\n\n## Next Section\n\nMore."
        result = render_page_sections(pt, content)
        assert "Call Graph" not in result
        assert "Graph content" not in result
        assert "Next Section" in result
        assert "More." in result

    def test_disabled_entity_diff_stripped(self):
        sections = (
            SectionDef(type="entity_diff", enabled=False),
        )
        pt = PageTemplate(file="test.md", sections=sections)
        content = "# Doc\n\n## Entity Diff\n\nDiff stuff.\n\n## Other\n\nKept."
        result = render_page_sections(pt, content)
        assert "Entity Diff" not in result
        assert "Diff stuff" not in result
        assert "Other" in result

    def test_multiple_sections_combined(self):
        sections = (
            SectionDef(type="intro", content="Welcome!", order=0),
            SectionDef(type="call_graph", enabled=False, order=1),
            SectionDef(
                type="custom",
                title="Deployment",
                content="Deploy via CI.",
                order=2,
            ),
            SectionDef(type="outro", content="End.", order=3),
        )
        pt = PageTemplate(file="arch.md", sections=sections)
        content = "# Architecture\n\nBody.\n\n## Call Graph\n\nGraph data.\n\n## Design\n\nDesign info."
        result = render_page_sections(pt, content)

        # Intro at start
        assert result.startswith("Welcome!")
        # Call graph removed
        assert "Call Graph" not in result
        assert "Graph data" not in result
        # Design kept
        assert "Design" in result
        # Custom section present
        assert "## Deployment" in result
        # Outro at end
        assert result.endswith("End.")

    def test_disabled_section_not_rendered(self):
        """Disabled sections with content should not render."""
        sections = (
            SectionDef(type="intro", content="Hidden", enabled=False),
        )
        pt = PageTemplate(file="test.md", sections=sections)
        result = render_page_sections(pt, "# Body")
        assert "Hidden" not in result


# ══════════════════════════════════════════════════════════════════════════════
# _strip_disabled_sections
# ══════════════════════════════════════════════════════════════════════════════


class TestStripDisabledSections:
    def test_empty_disabled_passthrough(self):
        content = "# Hello\n\n## Section\n\nBody."
        assert _strip_disabled_sections(content, set()) == content

    def test_strip_h2_section(self):
        content = "# Doc\n\n## Dependency Graph\n\nGraph.\n\n## Other\n\nKept."
        result = _strip_disabled_sections(content, {"call_graph"})
        assert "Dependency Graph" not in result
        assert "Other" in result

    def test_strip_h3_section(self):
        content = "# Doc\n\n### Call Tree\n\nTree.\n\n### Next\n\nKept."
        result = _strip_disabled_sections(content, {"call_graph"})
        assert "Call Tree" not in result
        assert "Next" in result

    def test_strip_diagram(self):
        content = "# Doc\n\n## Architecture Diagram\n\n```mermaid\ngraph TD\n```\n\n## Rest\n\nKept."
        result = _strip_disabled_sections(content, {"diagram"})
        assert "Architecture Diagram" not in result
        assert "mermaid" not in result
        assert "Rest" in result

    def test_strip_multiple_types(self):
        content = (
            "# Doc\n\n"
            "## Call Graph\n\nG.\n\n"
            "## Entity Diff\n\nD.\n\n"
            "## Summary\n\nS."
        )
        result = _strip_disabled_sections(content, {"call_graph", "entity_diff"})
        assert "Call Graph" not in result
        assert "Entity Diff" not in result
        assert "Summary" in result

    def test_no_matching_headings(self):
        content = "# Doc\n\n## Unrelated\n\nContent."
        result = _strip_disabled_sections(content, {"call_graph"})
        assert result == content

    def test_last_section_stripped(self):
        """Stripping the last section in a doc (no next heading)."""
        content = "# Doc\n\nIntro.\n\n## Call Graph\n\nGraph content here."
        result = _strip_disabled_sections(content, {"call_graph"})
        assert "Call Graph" not in result
        assert "Graph content" not in result
        assert "Intro." in result


# ══════════════════════════════════════════════════════════════════════════════
# VALID_SECTION_TYPES
# ══════════════════════════════════════════════════════════════════════════════


class TestValidSectionTypes:
    def test_known_types(self):
        expected = {
            "intro", "outro", "call_graph", "entity_diff",
            "diagram", "data_models", "api_surface", "custom",
        }
        assert VALID_SECTION_TYPES == expected
