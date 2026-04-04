"""Tests for coverage file auto-detection."""

import json

import pytest

from repoforge.coverage.detector import auto_detect_and_parse, detect_coverage_files

MINIMAL_COBERTURA = """\
<?xml version="1.0" ?>
<coverage line-rate="0.8">
  <packages>
    <package name="app">
      <classes>
        <class name="main.py" filename="app/main.py" line-rate="0.8">
          <lines><line number="1" hits="1"/><line number="2" hits="0"/></lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
"""

MINIMAL_LCOV = """\
TN:
SF:src/index.ts
LF:10
LH:8
end_of_record
"""

MINIMAL_COVERAGE_PY = json.dumps({
    "meta": {"version": "7.0"},
    "files": {
        "app/main.py": {
            "summary": {"covered_lines": 8, "missing_lines": 2, "percent_covered": 80.0},
        },
    },
})


class TestDetectCoverageFiles:

    def test_detects_cobertura(self, tmp_path):
        (tmp_path / "coverage.xml").write_text(MINIMAL_COBERTURA)
        found = detect_coverage_files(tmp_path)
        assert len(found) >= 1
        formats = {fmt for _, fmt in found}
        assert "cobertura" in formats

    def test_detects_lcov(self, tmp_path):
        (tmp_path / "lcov.info").write_text(MINIMAL_LCOV)
        found = detect_coverage_files(tmp_path)
        formats = {fmt for _, fmt in found}
        assert "lcov" in formats

    def test_detects_coverage_py(self, tmp_path):
        (tmp_path / "coverage.json").write_text(MINIMAL_COVERAGE_PY)
        found = detect_coverage_files(tmp_path)
        formats = {fmt for _, fmt in found}
        assert "coverage_py" in formats

    def test_detects_nested_file(self, tmp_path):
        sub = tmp_path / "build" / "reports"
        sub.mkdir(parents=True)
        (sub / "coverage.xml").write_text(MINIMAL_COBERTURA)
        found = detect_coverage_files(tmp_path)
        # build is in _SKIP_DIRS so this should NOT be found
        cobertura = [f for _, f in found if f == "cobertura"]
        assert len(cobertura) == 0

    def test_detects_in_coverage_dir(self, tmp_path):
        cov = tmp_path / "coverage"
        cov.mkdir()
        (cov / "lcov.info").write_text(MINIMAL_LCOV)
        found = detect_coverage_files(tmp_path)
        formats = {fmt for _, fmt in found}
        assert "lcov" in formats

    def test_ignores_non_coverage_json(self, tmp_path):
        (tmp_path / "coverage.json").write_text('{"not": "coverage"}')
        found = detect_coverage_files(tmp_path)
        # Should not match because validation fails
        assert len(found) == 0

    def test_multiple_formats(self, tmp_path):
        (tmp_path / "coverage.xml").write_text(MINIMAL_COBERTURA)
        (tmp_path / "lcov.info").write_text(MINIMAL_LCOV)
        found = detect_coverage_files(tmp_path)
        formats = {fmt for _, fmt in found}
        assert "cobertura" in formats
        assert "lcov" in formats

    def test_empty_dir(self, tmp_path):
        found = detect_coverage_files(tmp_path)
        assert found == []


class TestAutoDetectAndParse:

    def test_parses_detected_files(self, tmp_path):
        (tmp_path / "coverage.xml").write_text(MINIMAL_COBERTURA)
        reports = auto_detect_and_parse(tmp_path)
        assert len(reports) == 1
        assert reports[0].source_format == "cobertura"
        assert len(reports[0].files) == 1

    def test_parses_multiple_formats(self, tmp_path):
        (tmp_path / "coverage.xml").write_text(MINIMAL_COBERTURA)
        (tmp_path / "lcov.info").write_text(MINIMAL_LCOV)
        reports = auto_detect_and_parse(tmp_path)
        assert len(reports) == 2
        formats = {r.source_format for r in reports}
        assert formats == {"cobertura", "lcov"}

    def test_empty_dir_returns_empty(self, tmp_path):
        reports = auto_detect_and_parse(tmp_path)
        assert reports == []

    def test_malformed_file_skipped(self, tmp_path):
        (tmp_path / "coverage.xml").write_text("<coverage><not valid xml")
        reports = auto_detect_and_parse(tmp_path)
        # Malformed XML won't validate as cobertura
        assert len(reports) == 0
