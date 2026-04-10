"""Semantic chunking — split content at meaning boundaries, not fixed sizes.

Detects where content meaning shifts by analyzing structural signals:
- Heading changes (## → new topic)
- Empty line clusters (paragraph breaks)
- Code block boundaries
- Import/function/class declarations (in source code)

Produces chunks that are semantically coherent, unlike naive line/token
splitting which can cut in the middle of a thought.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    """A semantically coherent block of content."""
    text: str
    start_line: int
    end_line: int
    kind: str  # "heading", "code", "prose", "declaration", "mixed"
    token_estimate: int

    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1


# ── Boundary detection ──

_HEADING_RE = re.compile(r"^#{1,6}\s+")
_CODE_FENCE_RE = re.compile(r"^```")
_DECLARATION_RE = re.compile(
    r"^(?:export\s+)?(?:function|class|interface|type|const|let|var|def|async\s+def|pub\s+fn|fn|struct|impl)\s+\w"
)
_IMPORT_RE = re.compile(r"^(?:import|from|require|use|#include)\s")
_BLANK_CLUSTER = 2  # consecutive blank lines = boundary


def _is_boundary(line: str, prev_blank_count: int) -> bool:
    """Check if a line represents a semantic boundary."""
    stripped = line.rstrip()
    if _HEADING_RE.match(stripped):
        return True
    if _CODE_FENCE_RE.match(stripped):
        return True
    if _DECLARATION_RE.match(stripped):
        return True
    if _IMPORT_RE.match(stripped) and prev_blank_count >= 1:
        return True
    if prev_blank_count >= _BLANK_CLUSTER:
        return True
    return False


def _classify_chunk(text: str) -> str:
    """Classify a chunk by its dominant content type."""
    lines = text.strip().split("\n")
    if not lines:
        return "mixed"
    first = lines[0].strip()
    if _HEADING_RE.match(first):
        return "heading"
    if _CODE_FENCE_RE.match(first):
        return "code"
    if _DECLARATION_RE.match(first):
        return "declaration"
    return "prose"


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ── Chunker ──

def chunk_content(
    content: str,
    *,
    max_chunk_tokens: int = 500,
    min_chunk_lines: int = 3,
) -> list[Chunk]:
    """Split content into semantic chunks at meaning boundaries.

    Args:
        content: The text to chunk.
        max_chunk_tokens: Soft maximum tokens per chunk. Chunks may exceed
            this if a single semantic block is larger.
        min_chunk_lines: Minimum lines to consider a boundary (avoids
            splitting very short sections).
    """
    if not content.strip():
        return []

    lines = content.split("\n")
    chunks: list[Chunk] = []
    current_lines: list[str] = []
    current_start = 0
    blank_count = 0
    in_code_block = False

    for i, line in enumerate(lines):
        stripped = line.rstrip()

        # Track code blocks (don't split inside them)
        if _CODE_FENCE_RE.match(stripped):
            in_code_block = not in_code_block

        # Track blank lines
        if not stripped:
            blank_count += 1
        else:
            # Check for boundary
            if (
                not in_code_block
                and current_lines
                and len(current_lines) >= min_chunk_lines
                and _is_boundary(stripped, blank_count)
            ):
                # Check token budget
                chunk_text = "\n".join(current_lines)
                if len(current_lines) >= min_chunk_lines:
                    chunks.append(Chunk(
                        text=chunk_text,
                        start_line=current_start + 1,
                        end_line=current_start + len(current_lines),
                        kind=_classify_chunk(chunk_text),
                        token_estimate=_estimate_tokens(chunk_text),
                    ))
                    current_lines = []
                    current_start = i

            blank_count = 0

        current_lines.append(line)

    # Flush remaining
    if current_lines:
        chunk_text = "\n".join(current_lines)
        chunks.append(Chunk(
            text=chunk_text,
            start_line=current_start + 1,
            end_line=current_start + len(current_lines),
            kind=_classify_chunk(chunk_text),
            token_estimate=_estimate_tokens(chunk_text),
        ))

    return chunks


def chunk_to_budget(
    chunks: list[Chunk], budget_tokens: int,
) -> list[Chunk]:
    """Select chunks that fit within a token budget, preserving order."""
    selected: list[Chunk] = []
    remaining = budget_tokens
    for chunk in chunks:
        if chunk.token_estimate <= remaining:
            selected.append(chunk)
            remaining -= chunk.token_estimate
        elif remaining <= 0:
            break
    return selected


def format_chunks(chunks: list[Chunk]) -> str:
    """Format chunks as a summary."""
    lines = [f"Chunks: {len(chunks)}, Total tokens: {sum(c.token_estimate for c in chunks)}"]
    for i, c in enumerate(chunks):
        lines.append(f"  [{i+1}] {c.kind} L{c.start_line}-{c.end_line} ({c.token_estimate} tok)")
    return "\n".join(lines)
