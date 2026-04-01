"""
extract.py - Content extraction from documentation text.

Parses markdown and HTML into structured DocContent.
Deterministic — no LLM needed.
"""

import re
from typing import Optional

from .types import CodeExample, DocContent, DocSection

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Markdown heading: # Title, ## Subtitle, etc.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# Fenced code block: ```lang\ncode\n```
_CODE_BLOCK_RE = re.compile(
    r"```(\w*)\n(.*?)```", re.DOTALL
)

# HTML tags (for stripping)
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Pattern indicators — lines that suggest a recommended pattern
_PATTERN_INDICATORS = [
    r"(?:you\s+)?(?:should|must|always|recommend|best\s+practice|prefer|use)\b",
    r"\bdo\b.*\binstead\b",
    r"\bcorrect\s+way\b",
    r"\bpattern\b",
]
_PATTERN_RE = re.compile(
    "|".join(_PATTERN_INDICATORS), re.IGNORECASE
)

# Anti-pattern indicators
_ANTI_PATTERN_INDICATORS = [
    r"\b(?:don'?t|do\s+not|never|avoid|anti.?pattern|bad\s+practice|deprecated)\b",
    r"\bwrong\s+way\b",
    r"\binstead\s+of\b",
]
_ANTI_PATTERN_RE = re.compile(
    "|".join(_ANTI_PATTERN_INDICATORS), re.IGNORECASE
)


def _strip_html(text: str) -> str:
    """Remove HTML tags, keeping text content and code blocks."""
    # Preserve <code> and <pre> content by replacing with markdown equivalents
    text = re.sub(
        r"<pre><code(?:\s+class=\"[^\"]*\")?>(.*?)</code></pre>",
        r"```\n\1\n```",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r"<code>(.*?)</code>", r"`\1`", text, flags=re.DOTALL)

    # Convert headings
    for level in range(1, 7):
        tag = f"h{level}"
        hashes = "#" * level
        text = re.sub(
            rf"<{tag}[^>]*>(.*?)</{tag}>",
            rf"\n{hashes} \1\n",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # Convert list items
    text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert paragraphs to double newlines
    text = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\1\n", text, flags=re.DOTALL | re.IGNORECASE)

    # Strip remaining tags
    text = _HTML_TAG_RE.sub("", text)

    # Decode HTML entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")

    return text.strip()


def _detect_if_html(text: str) -> bool:
    """Heuristic: does this look like HTML?"""
    return bool(
        re.search(r"<(?:html|head|body|div|p|h[1-6])\b", text, re.IGNORECASE)
    )


def _extract_sections(text: str) -> list[DocSection]:
    """Extract heading-delimited sections from markdown text."""
    sections: list[DocSection] = []
    headings = list(_HEADING_RE.finditer(text))

    if not headings:
        # No headings — treat entire text as one section
        content = text.strip()
        if content:
            sections.append(DocSection(heading="Content", level=1, content=content))
        return sections

    # Content before first heading
    pre = text[: headings[0].start()].strip()
    if pre:
        sections.append(DocSection(heading="Introduction", level=1, content=pre))

    for i, match in enumerate(headings):
        level = len(match.group(1))
        heading = match.group(2).strip()
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append(DocSection(heading=heading, level=level, content=content))

    return sections


def _extract_code_examples(text: str) -> list[CodeExample]:
    """Extract fenced code blocks with their surrounding context."""
    examples: list[CodeExample] = []
    headings = list(_HEADING_RE.finditer(text))

    for match in _CODE_BLOCK_RE.finditer(text):
        lang = match.group(1) or "text"
        code = match.group(2).strip()
        if not code:
            continue

        # Find the nearest preceding heading for context
        context = "General"
        pos = match.start()
        for h in reversed(headings):
            if h.start() < pos:
                context = h.group(2).strip()
                break

        examples.append(CodeExample(language=lang, code=code, context=context))

    return examples


def _extract_patterns(sections: list[DocSection]) -> tuple[list[str], list[str]]:
    """Extract pattern and anti-pattern statements from sections."""
    patterns: list[str] = []
    anti_patterns: list[str] = []

    for section in sections:
        for line in section.content.split("\n"):
            line_stripped = line.strip().lstrip("- *>")
            if not line_stripped or len(line_stripped) < 10:
                continue

            if _ANTI_PATTERN_RE.search(line_stripped):
                anti_patterns.append(line_stripped)
            elif _PATTERN_RE.search(line_stripped):
                patterns.append(line_stripped)

    # Deduplicate while preserving order
    seen_p: set[str] = set()
    unique_patterns = []
    for p in patterns:
        normalized = p.lower()
        if normalized not in seen_p:
            seen_p.add(normalized)
            unique_patterns.append(p)

    seen_a: set[str] = set()
    unique_anti = []
    for a in anti_patterns:
        normalized = a.lower()
        if normalized not in seen_a:
            seen_a.add(normalized)
            unique_anti.append(a)

    return unique_patterns[:20], unique_anti[:10]


def _infer_title(text: str, sections: list[DocSection], source: str) -> str:
    """Infer a title from the first H1 heading or source name."""
    # Check raw text for H1 headings first (sections may skip empty-content headings)
    h1_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if h1_match:
        return h1_match.group(1).strip()
    for s in sections:
        if s.level == 1:
            return s.heading
    # Fallback: derive from source
    source_clean = source.rstrip("/").split("/")[-1]
    source_clean = re.sub(r"[._-]+", " ", source_clean).title()
    return source_clean or "Documentation"


def extract_from_text(text: str, source: str = "") -> DocContent:
    """Extract structured content from a single text document.

    Handles both markdown and HTML (auto-detected).
    """
    if _detect_if_html(text):
        text = _strip_html(text)

    sections = _extract_sections(text)
    code_examples = _extract_code_examples(text)
    patterns, anti_patterns = _extract_patterns(sections)
    title = _infer_title(text, sections, source)

    return DocContent(
        title=title,
        source=source,
        sections=sections,
        code_examples=code_examples,
        patterns=patterns,
        anti_patterns=anti_patterns,
    )


def extract_content(
    raw_texts: list[str],
    source: str = "",
) -> DocContent:
    """Extract and merge content from multiple raw text documents.

    This is the main entry point for the extraction pipeline.
    """
    if not raw_texts:
        return DocContent(title="Empty", source=source)

    # Extract from each document
    docs = [extract_from_text(text, source) for text in raw_texts]

    # Merge into one DocContent
    title = docs[0].title
    all_sections: list[DocSection] = []
    all_examples: list[CodeExample] = []
    all_patterns: list[str] = []
    all_anti: list[str] = []

    for doc in docs:
        all_sections.extend(doc.sections)
        all_examples.extend(doc.code_examples)
        all_patterns.extend(doc.patterns)
        all_anti.extend(doc.anti_patterns)

    # Deduplicate patterns
    seen: set[str] = set()
    unique_patterns = []
    for p in all_patterns:
        if p.lower() not in seen:
            seen.add(p.lower())
            unique_patterns.append(p)

    seen_a: set[str] = set()
    unique_anti = []
    for a in all_anti:
        if a.lower() not in seen_a:
            seen_a.add(a.lower())
            unique_anti.append(a)

    return DocContent(
        title=title,
        source=source,
        sections=all_sections,
        code_examples=all_examples[:30],  # cap examples
        patterns=unique_patterns[:20],
        anti_patterns=unique_anti[:10],
    )
