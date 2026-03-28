"""Tests for Wave 5: Documentation quality scoring."""

import pytest

from repoforge.scoring import DocScorer, DocScore


GOOD_CHAPTER = """# Architecture

## Overview

The system uses a layered architecture with clear separation of concerns.

## Components

| Component | Purpose | File |
|-----------|---------|------|
| API Server | HTTP endpoints | `server.py` |
| Store | Data persistence | `store.py` |
| Config | Configuration | `config.py` |

## Data Flow

```mermaid
graph LR
    Client --> API --> Store --> DB
```

## Key Decisions

- **Why SQLite**: Embedded, zero-config, sufficient for single-node deployments.
- **Why HTTP**: Standard protocol, easy to test with curl.

## Error Handling

Errors propagate from Store → API → Client with structured JSON responses.

```python
class AppError(Exception):
    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
```
"""

WEAK_CHAPTER = """# Overview

This is a project.

It does stuff.
"""

EMPTY_CHAPTER = ""


# ── DocScore dataclass ───────────────────────────────────────────────────


class TestDocScore:

    def test_grade_pass(self):
        score = DocScore(file_path="test.md", overall=0.9)
        assert score.grade == "PASS"

    def test_grade_warn(self):
        score = DocScore(file_path="test.md", overall=0.7)
        assert score.grade == "WARN"

    def test_grade_fail(self):
        score = DocScore(file_path="test.md", overall=0.3)
        assert score.grade == "FAIL"


# ── Rule-based scoring (no LLM) ─────────────────────────────────────────


class TestStructureScore:

    def test_good_chapter_has_headings(self):
        scorer = DocScorer()
        score = scorer.score_content(GOOD_CHAPTER, "03-architecture.md")
        assert score.structure >= 0.5

    def test_empty_chapter_scores_zero(self):
        scorer = DocScorer()
        score = scorer.score_content(EMPTY_CHAPTER, "test.md")
        assert score.structure == 0.0

    def test_weak_chapter_low_structure(self):
        scorer = DocScorer()
        score = scorer.score_content(WEAK_CHAPTER, "test.md")
        assert score.structure < 0.7


class TestCompletenessScore:

    def test_good_chapter_has_tables_and_diagrams(self):
        scorer = DocScorer()
        score = scorer.score_content(GOOD_CHAPTER, "03-architecture.md")
        assert score.completeness >= 0.5

    def test_weak_chapter_low_completeness(self):
        scorer = DocScorer()
        score = scorer.score_content(WEAK_CHAPTER, "test.md")
        assert score.completeness < 0.5


class TestCodeQualityScore:

    def test_chapter_with_code_blocks(self):
        scorer = DocScorer()
        score = scorer.score_content(GOOD_CHAPTER, "test.md")
        assert score.code_quality >= 0.3

    def test_chapter_without_code(self):
        scorer = DocScorer()
        score = scorer.score_content(WEAK_CHAPTER, "test.md")
        assert score.code_quality == 0.0


class TestOverallScore:

    def test_overall_is_weighted_average(self):
        scorer = DocScorer()
        score = scorer.score_content(GOOD_CHAPTER, "03-architecture.md")
        assert 0.0 <= score.overall <= 1.0

    def test_good_chapter_scores_high(self):
        scorer = DocScorer()
        score = scorer.score_content(GOOD_CHAPTER, "03-architecture.md")
        assert score.overall >= 0.5

    def test_weak_chapter_scores_low(self):
        scorer = DocScorer()
        score = scorer.score_content(WEAK_CHAPTER, "test.md")
        assert score.overall < 0.5


# ── Score directory ──────────────────────────────────────────────────────


class TestScoreDirectory:

    def test_score_docs_directory(self, tmp_path):
        (tmp_path / "01-overview.md").write_text(GOOD_CHAPTER)
        (tmp_path / "02-quickstart.md").write_text(WEAK_CHAPTER)
        scorer = DocScorer()
        scores = scorer.score_directory(str(tmp_path))
        assert len(scores) == 2
        assert all(isinstance(s, DocScore) for s in scores)

    def test_empty_directory(self, tmp_path):
        scorer = DocScorer()
        scores = scorer.score_directory(str(tmp_path))
        assert scores == []


# ── Report formatting ────────────────────────────────────────────────────


class TestReport:

    def test_table_format(self, tmp_path):
        (tmp_path / "01-overview.md").write_text(GOOD_CHAPTER)
        scorer = DocScorer()
        scores = scorer.score_directory(str(tmp_path))
        report = scorer.report(scores, fmt="table")
        assert "01-overview.md" in report

    def test_json_format(self, tmp_path):
        import json
        (tmp_path / "01-overview.md").write_text(GOOD_CHAPTER)
        scorer = DocScorer()
        scores = scorer.score_directory(str(tmp_path))
        report = scorer.report(scores, fmt="json")
        parsed = json.loads(report)
        assert isinstance(parsed, list)
        assert parsed[0]["file_path"] == "01-overview.md"
