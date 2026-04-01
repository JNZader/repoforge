"""Tests for the unified coverage data model."""

from repoforge.coverage.model import CoverageFile, CoverageReport


class TestCoverageFile:

    def test_defaults(self):
        f = CoverageFile(path="src/main.py", line_rate=0.85)
        assert f.path == "src/main.py"
        assert f.line_rate == 0.85
        assert f.branch_rate is None
        assert f.function_rate is None
        assert f.lines_covered == 0
        assert f.lines_total == 0

    def test_all_fields(self):
        f = CoverageFile(
            path="app.ts",
            line_rate=0.90,
            branch_rate=0.75,
            function_rate=1.0,
            lines_covered=90,
            lines_total=100,
            branches_covered=6,
            branches_total=8,
            functions_covered=10,
            functions_total=10,
        )
        assert f.branches_covered == 6
        assert f.function_rate == 1.0


class TestCoverageReport:

    def _make_report(self, files=None):
        return CoverageReport(
            source_format="test",
            source_file="test.xml",
            files=files or [],
        )

    def test_empty_report_rates(self):
        r = self._make_report()
        assert r.overall_line_rate == 0.0
        assert r.overall_branch_rate is None
        assert r.overall_function_rate is None
        assert r.total_lines == 0

    def test_overall_line_rate(self):
        files = [
            CoverageFile(path="a.py", line_rate=0.5, lines_covered=50, lines_total=100),
            CoverageFile(path="b.py", line_rate=1.0, lines_covered=100, lines_total=100),
        ]
        r = self._make_report(files)
        assert r.total_lines == 200
        assert r.total_lines_covered == 150
        assert r.overall_line_rate == 0.75

    def test_overall_branch_rate(self):
        files = [
            CoverageFile(path="a.py", line_rate=1.0, branches_covered=3, branches_total=4),
            CoverageFile(path="b.py", line_rate=1.0, branches_covered=7, branches_total=16),
        ]
        r = self._make_report(files)
        assert r.total_branches == 20
        assert r.total_branches_covered == 10
        assert r.overall_branch_rate == 0.5

    def test_overall_function_rate(self):
        files = [
            CoverageFile(path="a.py", line_rate=1.0, functions_covered=2, functions_total=5),
            CoverageFile(path="b.py", line_rate=1.0, functions_covered=3, functions_total=5),
        ]
        r = self._make_report(files)
        assert r.overall_function_rate == 0.5

    def test_no_branches_returns_none(self):
        files = [
            CoverageFile(path="a.py", line_rate=1.0, lines_covered=10, lines_total=10),
        ]
        r = self._make_report(files)
        assert r.overall_branch_rate is None
