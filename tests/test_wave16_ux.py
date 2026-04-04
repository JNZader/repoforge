"""Tests for Wave 16: UX polish — progress tracking, diff viewer, summary formatter."""

import pytest

from repoforge.ux import (
    DiffResult,
    ProgressTracker,
    diff_docs,
    format_summary,
)

# ── ProgressTracker ──────────────────────────────────────────────────────


class TestProgressTracker:

    def test_tracks_total_and_completed(self):
        tracker = ProgressTracker(total=5, label="Generating")
        assert tracker.total == 5
        assert tracker.completed == 0

    def test_advance_increments(self):
        tracker = ProgressTracker(total=3)
        tracker.advance("01-overview.md")
        assert tracker.completed == 1
        tracker.advance("02-quickstart.md")
        assert tracker.completed == 2

    def test_percentage(self):
        tracker = ProgressTracker(total=4)
        assert tracker.percentage == 0.0
        tracker.advance("ch1")
        assert tracker.percentage == 25.0
        tracker.advance("ch2")
        assert tracker.percentage == 50.0

    def test_is_done(self):
        tracker = ProgressTracker(total=2)
        assert tracker.is_done is False
        tracker.advance("ch1")
        tracker.advance("ch2")
        assert tracker.is_done is True

    def test_format_progress_bar(self):
        tracker = ProgressTracker(total=4, label="Docs")
        tracker.advance("ch1")
        tracker.advance("ch2")
        bar = tracker.format_bar(width=20)
        assert "Docs" in bar
        assert "50%" in bar or "2/4" in bar

    def test_history_tracked(self):
        tracker = ProgressTracker(total=3)
        tracker.advance("ch1", status="ok")
        tracker.advance("ch2", status="error")
        assert len(tracker.history) == 2
        assert tracker.history[0]["item"] == "ch1"
        assert tracker.history[1]["status"] == "error"

    def test_zero_total_safe(self):
        tracker = ProgressTracker(total=0)
        assert tracker.percentage == 100.0
        assert tracker.is_done is True


# ── Diff viewer ──────────────────────────────────────────────────────────


class TestDiffDocs:

    def test_no_changes(self):
        result = diff_docs("# Title\n\nContent.", "# Title\n\nContent.")
        assert isinstance(result, DiffResult)
        assert result.has_changes is False

    def test_detects_addition(self):
        old = "# Title\n\nParagraph one."
        new = "# Title\n\nParagraph one.\n\nParagraph two."
        result = diff_docs(old, new)
        assert result.has_changes is True
        assert result.additions > 0

    def test_detects_deletion(self):
        old = "# Title\n\nParagraph one.\n\nParagraph two."
        new = "# Title\n\nParagraph one."
        result = diff_docs(old, new)
        assert result.has_changes is True
        assert result.deletions > 0

    def test_detects_modification(self):
        old = "# Title\n\nOld content here."
        new = "# Title\n\nNew content here."
        result = diff_docs(old, new)
        assert result.has_changes is True

    def test_format_unified(self):
        old = "Line one.\nLine two."
        new = "Line one.\nLine three."
        result = diff_docs(old, new)
        unified = result.format_unified()
        assert "-" in unified or "+" in unified

    def test_empty_inputs(self):
        result = diff_docs("", "")
        assert result.has_changes is False

    def test_summary_line(self):
        old = "A\nB\nC"
        new = "A\nD\nC\nE"
        result = diff_docs(old, new)
        summary = result.summary()
        assert isinstance(summary, str)


# ── Summary formatter ────────────────────────────────────────────────────


class TestFormatSummary:

    def test_formats_generation_summary(self):
        result = format_summary(
            project_name="TestProject",
            chapters_generated=7,
            total_tokens=35000,
            cost=0.04,
            duration_seconds=45.2,
            errors=0,
        )
        assert "TestProject" in result
        assert "7" in result

    def test_includes_cost(self):
        result = format_summary(
            project_name="App", chapters_generated=3,
            total_tokens=10000, cost=0.02, duration_seconds=20.0,
        )
        assert "$" in result

    def test_includes_duration(self):
        result = format_summary(
            project_name="App", chapters_generated=3,
            total_tokens=10000, cost=0.01, duration_seconds=65.0,
        )
        assert "1m" in result or "65" in result

    def test_shows_errors_if_any(self):
        result = format_summary(
            project_name="App", chapters_generated=5,
            total_tokens=10000, cost=0.01, duration_seconds=30.0,
            errors=2,
        )
        assert "2" in result and "error" in result.lower()

    def test_zero_cost_ok(self):
        result = format_summary(
            project_name="App", chapters_generated=3,
            total_tokens=0, cost=0.0, duration_seconds=5.0,
        )
        assert isinstance(result, str)
