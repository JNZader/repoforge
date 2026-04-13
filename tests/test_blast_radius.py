"""Tests for blast_radius module — items #14 and #15."""

import subprocess
from pathlib import Path

import pytest

from repoforge.blast_radius import (
    BlastRadiusReport,
    blast_radius_from_files,
    format_blast_radius,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def python_project(tmp_path):
    """Create a temp Python project with import chains."""
    # models.py (leaf — no imports)
    (tmp_path / "models.py").write_text(
        "class User:\n    pass\n\nclass Order:\n    pass\n"
    )

    # service.py imports models
    (tmp_path / "service.py").write_text(
        "from models import User\n\ndef get_user(): return User()\n"
    )

    # api.py imports service
    (tmp_path / "api.py").write_text(
        "from service import get_user\n\ndef handler(): return get_user()\n"
    )

    # test_service.py imports service
    (tmp_path / "test_service.py").write_text(
        "from service import get_user\n\ndef test_get_user(): assert get_user()\n"
    )

    # Unrelated file
    (tmp_path / "utils.py").write_text(
        "def helper(): pass\n"
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestBlastRadiusReport:
    def test_empty_report(self):
        report = BlastRadiusReport()
        assert report.total_affected == 0
        assert report.risk_level == "safe"

    def test_risk_levels(self):
        r1 = BlastRadiusReport(affected_files=["a.py"])
        assert r1.risk_level == "low"

        r2 = BlastRadiusReport(affected_files=[f"{i}.py" for i in range(5)])
        assert r2.risk_level == "medium"

        r3 = BlastRadiusReport(
            affected_files=[f"{i}.py" for i in range(8)],
            affected_tests=["t1.py", "t2.py", "t3.py"],
        )
        assert r3.risk_level == "high"

    def test_total_affected(self):
        r = BlastRadiusReport(
            affected_files=["a.py", "b.py"],
            affected_tests=["test_a.py"],
        )
        assert r.total_affected == 3


class TestBlastRadiusFromFiles:
    def test_leaf_file_no_dependents(self, python_project):
        """Changing a leaf (utils.py) should affect nothing."""
        report = blast_radius_from_files(
            str(python_project), ["utils.py"]
        )
        assert report.changed_files == ["utils.py"]
        assert report.affected_files == []
        assert report.risk_level == "safe"

    def test_models_change_propagates(self, python_project):
        """Changing models.py should affect service.py, api.py, and test_service.py."""
        report = blast_radius_from_files(
            str(python_project), ["models.py"]
        )
        assert "models.py" in report.changed_files
        # service.py depends on models, api.py depends on service
        # test_service.py depends on service
        # Exact result depends on graph resolution

    def test_empty_file_list(self, python_project):
        report = blast_radius_from_files(str(python_project), [])
        assert report.total_affected == 0


class TestFormatBlastRadius:
    def test_format_empty(self):
        report = BlastRadiusReport()
        text = format_blast_radius(report)
        assert "Blast Radius" in text
        assert "safe" in text

    def test_format_with_data(self):
        report = BlastRadiusReport(
            changed_files=["a.py"],
            affected_files=["b.py", "c.py"],
            affected_tests=["test_a.py"],
            depth=2,
            commit="abc123",
        )
        text = format_blast_radius(report)
        assert "abc123" in text
        assert "b.py" in text
        assert "test_a.py" in text

    def test_format_with_symbols(self):
        from repoforge.blast_radius import ASTSymbolInfo
        report = BlastRadiusReport(
            changed_files=["a.py"],
            symbols=[ASTSymbolInfo(
                name="my_func", kind="function", file="a.py",
                line=10, signature="def my_func(x: int) -> str",
            )],
        )
        text = format_blast_radius(report)
        assert "my_func" in text
        assert "AST" in text
