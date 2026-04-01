"""Tests for skills_from_docs.generate module."""

import pytest

from repoforge.skills_from_docs.generate import generate_skill_md, _to_kebab_case
from repoforge.skills_from_docs.types import CodeExample, DocContent, DocSection


class TestToKebabCase:
    def test_simple(self):
        assert _to_kebab_case("React Guide") == "react-guide"

    def test_special_chars(self):
        assert _to_kebab_case("Vue.js 3 - Composition API") == "vuejs-3-composition-api"

    def test_underscores(self):
        assert _to_kebab_case("my_library_name") == "my-library-name"

    def test_truncates_long(self):
        result = _to_kebab_case("a" * 100)
        assert len(result) <= 50


class TestGenerateSkillMd:
    def test_has_yaml_frontmatter(self):
        doc = DocContent(
            title="React Hooks",
            source="https://reactjs.org",
            sections=[DocSection(heading="React Hooks", level=1, content="Hooks are functions.")],
        )
        result = generate_skill_md(doc)
        assert result.startswith("---\n")
        assert "name: react-hooks" in result
        assert "description:" in result
        assert 'version: "1.0"' in result
        assert "license: Apache-2.0" in result

    def test_custom_name(self):
        doc = DocContent(title="Some Lib", source="/tmp")
        result = generate_skill_md(doc, name="my-custom-skill")
        assert "name: my-custom-skill" in result

    def test_includes_code_examples(self):
        doc = DocContent(
            title="Test Lib",
            source="/tmp",
            sections=[DocSection(heading="Test Lib", level=1, content="A library.")],
            code_examples=[
                CodeExample(language="python", code="import test_lib", context="Installation"),
            ],
        )
        result = generate_skill_md(doc)
        assert "```python" in result
        assert "import test_lib" in result

    def test_includes_patterns_as_rules(self):
        doc = DocContent(
            title="Test",
            source="/tmp",
            patterns=["Always use type annotations", "Prefer immutable data structures"],
            anti_patterns=["Don't use global variables"],
        )
        result = generate_skill_md(doc)
        assert "Critical Rules" in result
        assert "Always use type annotations" in result
        assert "Don't use global variables" in result

    def test_includes_key_concepts(self):
        doc = DocContent(
            title="Test",
            source="/tmp",
            sections=[
                DocSection(heading="Test", level=1, content="Overview."),
                DocSection(heading="Components", level=2, content="Components are reusable UI pieces."),
                DocSection(heading="State", level=2, content="State manages data flow."),
            ],
        )
        result = generate_skill_md(doc)
        assert "Key Concepts" in result
        assert "Components" in result

    def test_source_in_metadata(self):
        doc = DocContent(title="Test", source="https://example.com/docs")
        result = generate_skill_md(doc)
        assert "source: https://example.com/docs" in result

    def test_empty_doc(self):
        doc = DocContent(title="Empty", source="/tmp")
        result = generate_skill_md(doc)
        assert "---\n" in result  # still has frontmatter
        assert "name: empty" in result
