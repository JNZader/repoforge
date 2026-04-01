"""Tests for skills_from_docs.types module."""

from repoforge.skills_from_docs.types import (
    CodeExample,
    DocContent,
    DocSection,
    SkillConflict,
    SourceType,
)


class TestSourceType:
    def test_enum_values(self):
        assert SourceType.URL.value == "url"
        assert SourceType.GITHUB_REPO.value == "github_repo"
        assert SourceType.LOCAL_DIR.value == "local_dir"


class TestDocContent:
    def test_default_fields(self):
        doc = DocContent(title="Test", source="/tmp")
        assert doc.title == "Test"
        assert doc.sections == []
        assert doc.code_examples == []
        assert doc.patterns == []
        assert doc.anti_patterns == []

    def test_with_sections(self):
        section = DocSection(heading="Intro", level=1, content="Hello")
        doc = DocContent(title="Test", source="/tmp", sections=[section])
        assert len(doc.sections) == 1
        assert doc.sections[0].heading == "Intro"


class TestSkillConflict:
    def test_fields(self):
        conflict = SkillConflict(
            existing_skill="react-19",
            generated_rule="Always use hooks",
            existing_rule="Never use hooks",
            description="Contradiction",
        )
        assert conflict.existing_skill == "react-19"
        assert "hooks" in conflict.generated_rule
