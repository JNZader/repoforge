"""Tests for skills_from_docs.extract module."""

import pytest

from repoforge.skills_from_docs.extract import (
    extract_content,
    extract_from_text,
)


class TestExtractFromText:
    def test_basic_markdown(self):
        text = "# My Library\n\nSome introduction.\n\n## Getting Started\n\nInstall it.\n"
        doc = extract_from_text(text, source="test")
        assert doc.title == "My Library"
        assert len(doc.sections) >= 2

    def test_extracts_code_examples(self):
        text = (
            "# Docs\n\n## Usage\n\n```python\nimport foo\nfoo.bar()\n```\n"
            "\n## Config\n\n```yaml\nkey: value\n```\n"
        )
        doc = extract_from_text(text)
        assert len(doc.code_examples) == 2
        assert doc.code_examples[0].language == "python"
        assert "import foo" in doc.code_examples[0].code
        assert doc.code_examples[0].context == "Usage"
        assert doc.code_examples[1].language == "yaml"

    def test_extracts_patterns(self):
        text = (
            "# Guide\n\n## Best Practices\n\n"
            "- You should always use type annotations\n"
            "- Prefer composition over inheritance\n"
            "- Use dependency injection for testability\n"
        )
        doc = extract_from_text(text)
        assert len(doc.patterns) >= 2

    def test_extracts_anti_patterns(self):
        text = (
            "# Guide\n\n## Common Mistakes\n\n"
            "- Don't use global state\n"
            "- Avoid mutable default arguments\n"
            "- Never import with wildcard\n"
        )
        doc = extract_from_text(text)
        assert len(doc.anti_patterns) >= 2

    def test_html_content(self):
        text = (
            "<html><body>"
            "<h1>React Guide</h1>"
            "<h2>Components</h2>"
            "<p>Components are the building blocks.</p>"
            "<pre><code class=\"jsx\">function App() { return <div/>; }</code></pre>"
            "</body></html>"
        )
        doc = extract_from_text(text)
        assert doc.title == "React Guide"
        assert len(doc.sections) >= 1

    def test_no_headings(self):
        text = "Just some plain text with no headings.\nAnother line."
        doc = extract_from_text(text)
        assert doc.title  # should still have a title
        assert len(doc.sections) >= 1

    def test_empty_text(self):
        doc = extract_from_text("", source="empty")
        assert doc.title  # fallback title from source

    def test_deduplicates_patterns(self):
        text = (
            "# Guide\n\n## Rules\n\n"
            "- Always use strict mode\n"
            "- always use strict mode\n"  # duplicate (case-insensitive)
            "- Use type checking\n"
        )
        doc = extract_from_text(text)
        # Should not have duplicates
        lowered = [p.lower() for p in doc.patterns]
        assert len(lowered) == len(set(lowered))


class TestExtractContent:
    def test_merges_multiple_docs(self):
        texts = [
            "# Doc One\n\n## Intro\n\nFirst doc content.\n",
            "# Doc Two\n\n## Setup\n\nSecond doc content.\n",
        ]
        doc = extract_content(texts, source="test")
        assert doc.title == "Doc One"  # takes first title
        assert len(doc.sections) >= 2  # sections from both docs
        headings = {s.heading for s in doc.sections}
        assert "Intro" in headings
        assert "Setup" in headings

    def test_empty_list(self):
        doc = extract_content([], source="empty")
        assert doc.title == "Empty"
        assert doc.sections == []

    def test_single_doc(self):
        texts = ["# Single\n\n## One Section\n\nContent here.\n"]
        doc = extract_content(texts, source="test")
        assert doc.title == "Single"

    def test_caps_code_examples(self):
        # Generate many code blocks
        blocks = "\n".join(
            f"```python\nprint({i})\n```\n" for i in range(50)
        )
        texts = [f"# Many Examples\n\n{blocks}"]
        doc = extract_content(texts)
        assert len(doc.code_examples) <= 30  # capped
