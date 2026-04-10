"""Tests for semantic_chunker — meaning-boundary content splitting."""

from repoforge.semantic_chunker import (
    Chunk,
    chunk_content,
    chunk_to_budget,
    format_chunks,
)

SAMPLE_MARKDOWN = """# Introduction

This is the introduction paragraph.
It explains the project goals.

## Architecture

The system uses hexagonal architecture.
Domain logic is isolated from infrastructure.

```python
class UserService:
    def __init__(self, repo: UserRepo):
        self.repo = repo
```

## Testing

We use pytest for all tests.
Coverage threshold is 85%.

## Deployment

Deploy via Docker Compose.
"""

SAMPLE_CODE = (
    "import os\n"
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "def authenticate(token: str) -> User:\n"
    "    # Validate and decode a JWT token.\n"
    "    payload = decode_jwt(token)\n"
    "    return User.from_payload(payload)\n"
    "\n"
    "\n"
    "def authorize(user: User, resource: str) -> bool:\n"
    "    # Check if user has access to resource.\n"
    "    return resource in user.permissions\n"
    "\n"
    "\n"
    "class UserService:\n"
    "    def __init__(self, db: Database):\n"
    "        self.db = db\n"
    "\n"
    "    def get_user(self, user_id: str) -> User:\n"
    "        return self.db.find_one(user_id)\n"
)


class TestChunkContent:
    def test_splits_at_headings(self):
        chunks = chunk_content(SAMPLE_MARKDOWN)
        assert len(chunks) >= 3  # at least intro, arch, testing, deploy

    def test_preserves_code_blocks(self):
        chunks = chunk_content(SAMPLE_MARKDOWN)
        # Code block should not be split
        code_chunks = [c for c in chunks if c.kind == "code" or "class UserService" in c.text]
        assert len(code_chunks) >= 1

    def test_splits_at_function_declarations(self):
        chunks = chunk_content(SAMPLE_CODE)
        assert len(chunks) >= 2  # at least imports+auth, authorize, UserService

    def test_chunk_has_correct_lines(self):
        chunks = chunk_content(SAMPLE_MARKDOWN)
        for chunk in chunks:
            assert chunk.start_line >= 1
            assert chunk.end_line >= chunk.start_line
            assert chunk.line_count > 0

    def test_chunk_has_token_estimate(self):
        chunks = chunk_content(SAMPLE_MARKDOWN)
        for chunk in chunks:
            assert chunk.token_estimate > 0

    def test_empty_content(self):
        assert chunk_content("") == []
        assert chunk_content("   \n\n  ") == []

    def test_single_line(self):
        chunks = chunk_content("Just one line of text.")
        assert len(chunks) == 1

    def test_min_chunk_lines_respected(self):
        # With min_chunk_lines=5, very short sections shouldn't split
        short = "line1\nline2\n## Heading\nline4"
        chunks = chunk_content(short, min_chunk_lines=5)
        assert len(chunks) == 1  # too short to split

    def test_all_text_preserved(self):
        chunks = chunk_content(SAMPLE_MARKDOWN)
        reconstructed = "\n".join(c.text for c in chunks)
        # All original lines should be present
        for line in SAMPLE_MARKDOWN.strip().split("\n"):
            if line.strip():
                assert line in reconstructed


class TestChunkToBudget:
    def test_selects_within_budget(self):
        chunks = chunk_content(SAMPLE_MARKDOWN)
        total = sum(c.token_estimate for c in chunks)
        budget = total // 2
        selected = chunk_to_budget(chunks, budget)
        assert sum(c.token_estimate for c in selected) <= budget
        assert len(selected) < len(chunks)

    def test_zero_budget(self):
        chunks = chunk_content(SAMPLE_MARKDOWN)
        assert chunk_to_budget(chunks, 0) == []

    def test_large_budget_returns_all(self):
        chunks = chunk_content(SAMPLE_MARKDOWN)
        selected = chunk_to_budget(chunks, 100_000)
        assert len(selected) == len(chunks)


class TestFormatChunks:
    def test_summary_format(self):
        chunks = chunk_content(SAMPLE_MARKDOWN)
        output = format_chunks(chunks)
        assert "Chunks:" in output
        assert "Total tokens:" in output

    def test_empty_chunks(self):
        assert "0" in format_chunks([])
