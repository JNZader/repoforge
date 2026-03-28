"""Documentation quality scoring — rule-based, no LLM required.

Scores generated documentation chapters across multiple dimensions:
- Structure: heading hierarchy, section count, depth
- Completeness: tables, diagrams, lists, cross-references
- Code quality: code blocks, language annotations, examples
- Clarity: sentence length, paragraph structure, word count

Usage:
    from repoforge.scoring import DocScorer
    scorer = DocScorer()
    score = scorer.score_content(markdown_content, "03-architecture.md")
    print(score.overall, score.grade)  # 0.82 WARN
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Dimension weights (must sum to 1.0)
_WEIGHTS = {
    "structure": 0.30,
    "completeness": 0.30,
    "code_quality": 0.15,
    "clarity": 0.25,
}


@dataclass
class DocScore:
    """Quality score for a single documentation chapter."""

    file_path: str
    structure: float = 0.0
    completeness: float = 0.0
    code_quality: float = 0.0
    clarity: float = 0.0
    overall: float = 0.0
    details: dict = field(default_factory=dict)

    @property
    def grade(self) -> str:
        if self.overall >= 0.85:
            return "PASS"
        if self.overall >= 0.60:
            return "WARN"
        return "FAIL"


class DocScorer:
    """Rule-based documentation quality scorer."""

    def score_content(self, content: str, file_path: str) -> DocScore:
        """Score a single chapter's markdown content."""
        score = DocScore(file_path=file_path)

        if not content or not content.strip():
            return score

        score.structure = self._score_structure(content)
        score.completeness = self._score_completeness(content)
        score.code_quality = self._score_code_quality(content)
        score.clarity = self._score_clarity(content)

        score.overall = (
            score.structure * _WEIGHTS["structure"]
            + score.completeness * _WEIGHTS["completeness"]
            + score.code_quality * _WEIGHTS["code_quality"]
            + score.clarity * _WEIGHTS["clarity"]
        )

        return score

    def score_file(self, path: str) -> DocScore:
        """Score a single markdown file."""
        p = Path(path)
        content = p.read_text(encoding="utf-8", errors="replace")
        return self.score_content(content, p.name)

    def score_directory(self, docs_dir: str) -> list[DocScore]:
        """Score all .md files in a directory."""
        p = Path(docs_dir)
        scores = []
        for md in sorted(p.glob("*.md")):
            scores.append(self.score_file(str(md)))
        return scores

    def report(self, scores: list[DocScore], fmt: str = "table") -> str:
        """Format scores as table, json, or markdown."""
        if fmt == "json":
            return self._report_json(scores)
        return self._report_table(scores)

    # -- Dimension scorers --------------------------------------------------

    def _score_structure(self, content: str) -> float:
        """Score heading hierarchy and section organization."""
        lines = content.split("\n")
        headings = [l for l in lines if l.startswith("#")]

        if not headings:
            return 0.0

        score = 0.0

        # Has H1
        h1s = [h for h in headings if h.startswith("# ") and not h.startswith("## ")]
        if h1s:
            score += 0.25

        # Has H2 sections
        h2s = [h for h in headings if h.startswith("## ")]
        if len(h2s) >= 2:
            score += 0.35
        elif len(h2s) == 1:
            score += 0.15

        # Has H3 subsections (depth)
        h3s = [h for h in headings if h.startswith("### ")]
        if h3s:
            score += 0.2

        # Reasonable section count (not too few, not too many)
        total = len(headings)
        if 3 <= total <= 15:
            score += 0.2
        elif total > 0:
            score += 0.1

        return min(score, 1.0)

    def _score_completeness(self, content: str) -> float:
        """Score presence of tables, diagrams, lists, links."""
        score = 0.0

        # Tables
        if re.search(r"\|.*\|.*\|", content):
            score += 0.25

        # Mermaid diagrams
        if "```mermaid" in content:
            score += 0.20

        # Bullet/numbered lists
        list_items = re.findall(r"^[\s]*[-*]\s", content, re.MULTILINE)
        if len(list_items) >= 3:
            score += 0.20
        elif list_items:
            score += 0.10

        # Bold text (key terms highlighted)
        bolds = re.findall(r"\*\*[^*]+\*\*", content)
        if len(bolds) >= 2:
            score += 0.15

        # Word count (substantial content)
        words = len(content.split())
        if words >= 300:
            score += 0.20
        elif words >= 100:
            score += 0.10

        return min(score, 1.0)

    def _score_code_quality(self, content: str) -> float:
        """Score code blocks — presence, language annotations, variety."""
        code_blocks = re.findall(r"```(\w*)", content)

        if not code_blocks:
            return 0.0

        score = 0.0

        # Has code blocks
        score += 0.3

        # Language-annotated blocks (```python, ```go, etc.)
        annotated = [b for b in code_blocks if b and b != "mermaid"]
        if annotated:
            score += 0.4

        # Multiple code blocks
        if len(code_blocks) >= 2:
            score += 0.3

        return min(score, 1.0)

    def _score_clarity(self, content: str) -> float:
        """Score readability — paragraph length, sentence variety."""
        if not content.strip():
            return 0.0

        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if not paragraphs:
            return 0.0

        score = 0.0

        # Has multiple paragraphs
        if len(paragraphs) >= 3:
            score += 0.3
        elif len(paragraphs) >= 2:
            score += 0.15

        # Sentences aren't too long (avg < 30 words)
        sentences = re.split(r"[.!?]+", content)
        sentences = [s.strip() for s in sentences if s.strip() and not s.strip().startswith("#")]
        if sentences:
            avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
            if avg_words <= 25:
                score += 0.3
            elif avg_words <= 40:
                score += 0.15

        # Word count indicates substance
        words = len(content.split())
        if words >= 200:
            score += 0.2
        elif words >= 50:
            score += 0.1

        # Not a wall of text — has formatting breaks
        lines = content.split("\n")
        blank_lines = sum(1 for l in lines if not l.strip())
        if blank_lines >= 3:
            score += 0.2

        return min(score, 1.0)

    # -- Report formatters --------------------------------------------------

    def _report_table(self, scores: list[DocScore]) -> str:
        lines = [
            f"{'File':<30} {'Structure':>9} {'Complete':>9} {'Code':>6} {'Clarity':>8} {'Overall':>8} {'Grade':>6}",
            "-" * 82,
        ]
        for s in scores:
            lines.append(
                f"{s.file_path:<30} {s.structure:>8.2f} {s.completeness:>9.2f} "
                f"{s.code_quality:>6.2f} {s.clarity:>8.2f} {s.overall:>8.2f} {s.grade:>6}"
            )
        return "\n".join(lines)

    def _report_json(self, scores: list[DocScore]) -> str:
        data = [
            {
                "file_path": s.file_path,
                "structure": round(s.structure, 3),
                "completeness": round(s.completeness, 3),
                "code_quality": round(s.code_quality, 3),
                "clarity": round(s.clarity, 3),
                "overall": round(s.overall, 3),
                "grade": s.grade,
            }
            for s in scores
        ]
        return json.dumps(data, indent=2)
