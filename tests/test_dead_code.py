"""Tests for dead_code module — item #20."""

from pathlib import Path

import pytest

from repoforge.dead_code import (
    DeadCodeReport,
    DeadSymbol,
    detect_dead_code,
    format_dead_code_report,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_with_dead_code(tmp_path):
    """Create a project where some symbols are never imported."""
    # models.py — exports User and Order, but Order is never imported
    (tmp_path / "models.py").write_text(
        "class User:\n    pass\n\n\n"
        "class Order:\n    pass\n\n\n"
        "def helper():\n    pass\n"
    )
    # service.py — imports User only
    (tmp_path / "service.py").write_text(
        "from models import User\n\n\n"
        "def get_user():\n    return User()\n"
    )
    # api.py — imports service
    (tmp_path / "api.py").write_text(
        "from service import get_user\n\n\n"
        "def handler():\n    return get_user()\n"
    )
    # orphan.py — nobody imports this
    (tmp_path / "orphan.py").write_text(
        "def lonely_function():\n    return 42\n"
    )
    return tmp_path


@pytest.fixture
def project_no_dead_code(tmp_path):
    """Create a project with full connectivity."""
    (tmp_path / "utils.py").write_text(
        "def add(a, b):\n    return a + b\n"
    )
    (tmp_path / "main.py").write_text(
        "from utils import add\n\n\nresult = add(1, 2)\n"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestDeadCodeReport:
    def test_empty_report(self):
        report = DeadCodeReport()
        assert report.isolated_modules == []
        assert report.dead_symbols == []

    def test_format_empty(self):
        report = DeadCodeReport(total_modules=5, total_exports=10)
        output = format_dead_code_report(report)
        assert "No dead code detected" in output


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestDetectDeadCode:
    def test_finds_isolated_modules(self, project_with_dead_code):
        report = detect_dead_code(str(project_with_dead_code))
        # orphan.py should be detected as isolated
        assert "orphan.py" in report.isolated_modules

    def test_finds_dead_symbols(self, project_with_dead_code):
        report = detect_dead_code(str(project_with_dead_code))
        dead_names = [s.name for s in report.dead_symbols]
        # Order and helper are exported but never imported by other files
        assert "Order" in dead_names or "helper" in dead_names

    def test_entry_points_excluded(self, project_no_dead_code):
        report = detect_dead_code(str(project_no_dead_code))
        # main.py is an entry point and should be excluded
        assert "main.py" in report.entry_points
        assert "main.py" not in report.isolated_modules

    def test_total_counts(self, project_with_dead_code):
        report = detect_dead_code(str(project_with_dead_code))
        assert report.total_modules > 0
        assert report.total_exports >= 0

    def test_empty_project(self, tmp_path):
        report = detect_dead_code(str(tmp_path))
        assert report.total_modules == 0


# ---------------------------------------------------------------------------
# Formatter tests
# ---------------------------------------------------------------------------


class TestFormatDeadCodeReport:
    def test_format_with_results(self):
        report = DeadCodeReport(
            isolated_modules=["orphan.py"],
            dead_symbols=[
                DeadSymbol(
                    name="unused_func", kind="function",
                    file="lib.py", confidence="high",
                ),
            ],
            total_modules=10,
            total_exports=30,
        )
        output = format_dead_code_report(report)
        assert "orphan.py" in output
        assert "unused_func" in output
        assert "high confidence" in output

    def test_format_groups_by_confidence(self):
        report = DeadCodeReport(
            dead_symbols=[
                DeadSymbol(name="a", kind="function", file="x.py", confidence="high"),
                DeadSymbol(name="b", kind="function", file="y.py", confidence="low"),
            ],
            total_modules=5,
            total_exports=10,
        )
        output = format_dead_code_report(report)
        # High confidence should appear before low
        high_pos = output.index("high confidence")
        low_pos = output.index("low confidence")
        assert high_pos < low_pos
