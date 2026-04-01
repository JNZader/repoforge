"""Tests for coverage markdown renderer."""

from repoforge.coverage.model import CoverageFile, CoverageReport
from repoforge.coverage.renderer import render_coverage_markdown


def _make_report(files, fmt="test"):
    return CoverageReport(source_format=fmt, source_file="test.xml", files=files)


class TestRenderCoverageMarkdown:

    def test_empty_reports(self):
        assert render_coverage_markdown([]) == ""

    def test_empty_files(self):
        r = _make_report([])
        assert render_coverage_markdown([r]) == ""

    def test_contains_header(self):
        r = _make_report([
            CoverageFile(path="a.py", line_rate=0.8, lines_covered=8, lines_total=10),
        ])
        md = render_coverage_markdown([r])
        assert "## Test Coverage" in md

    def test_contains_summary_table(self):
        r = _make_report([
            CoverageFile(path="a.py", line_rate=0.8, lines_covered=80, lines_total=100),
        ])
        md = render_coverage_markdown([r])
        assert "| Lines |" in md
        assert "80.0%" in md

    def test_branch_coverage_shown(self):
        r = _make_report([
            CoverageFile(
                path="a.py", line_rate=0.8,
                lines_covered=8, lines_total=10,
                branches_covered=6, branches_total=10,
            ),
        ])
        md = render_coverage_markdown([r])
        assert "Branches" in md
        assert "60.0%" in md

    def test_function_coverage_shown(self):
        r = _make_report([
            CoverageFile(
                path="a.py", line_rate=0.8,
                lines_covered=8, lines_total=10,
                functions_covered=9, functions_total=10,
            ),
        ])
        md = render_coverage_markdown([r])
        assert "Functions" in md
        assert "90.0%" in md

    def test_per_file_table(self):
        r = _make_report([
            CoverageFile(path="src/main.py", line_rate=0.9, lines_covered=9, lines_total=10),
            CoverageFile(path="src/utils.py", line_rate=0.5, lines_covered=5, lines_total=10),
        ])
        md = render_coverage_markdown([r])
        assert "`src/main.py`" in md
        assert "`src/utils.py`" in md

    def test_files_sorted_worst_first(self):
        r = _make_report([
            CoverageFile(path="good.py", line_rate=0.95, lines_covered=95, lines_total=100),
            CoverageFile(path="bad.py", line_rate=0.20, lines_covered=20, lines_total=100),
            CoverageFile(path="mid.py", line_rate=0.60, lines_covered=60, lines_total=100),
        ])
        md = render_coverage_markdown([r])
        bad_pos = md.index("bad.py")
        mid_pos = md.index("mid.py")
        good_pos = md.index("good.py")
        assert bad_pos < mid_pos < good_pos

    def test_high_badge(self):
        r = _make_report([
            CoverageFile(path="a.py", line_rate=0.85, lines_covered=85, lines_total=100),
        ])
        md = render_coverage_markdown([r])
        assert "HIGH" in md

    def test_medium_badge(self):
        r = _make_report([
            CoverageFile(path="a.py", line_rate=0.65, lines_covered=65, lines_total=100),
        ])
        md = render_coverage_markdown([r])
        assert "MEDIUM" in md

    def test_low_badge(self):
        r = _make_report([
            CoverageFile(path="a.py", line_rate=0.3, lines_covered=30, lines_total=100),
        ])
        md = render_coverage_markdown([r])
        assert "LOW" in md

    def test_multiple_reports_merged(self):
        r1 = _make_report([
            CoverageFile(path="a.py", line_rate=0.8, lines_covered=80, lines_total=100),
        ], fmt="cobertura")
        r2 = _make_report([
            CoverageFile(path="b.ts", line_rate=0.6, lines_covered=60, lines_total=100),
        ], fmt="lcov")
        md = render_coverage_markdown([r1, r2])
        assert "`a.py`" in md
        assert "`b.ts`" in md
        assert "70.0%" in md  # overall: 140/200

    def test_source_format_shown(self):
        r = _make_report([
            CoverageFile(path="a.py", line_rate=1.0, lines_covered=10, lines_total=10),
        ], fmt="cobertura")
        md = render_coverage_markdown([r])
        assert "cobertura" in md

    def test_caps_at_30_files(self):
        files = [
            CoverageFile(path=f"file_{i}.py", line_rate=0.5, lines_covered=5, lines_total=10)
            for i in range(40)
        ]
        r = _make_report(files)
        md = render_coverage_markdown([r])
        assert "and 10 more files" in md
