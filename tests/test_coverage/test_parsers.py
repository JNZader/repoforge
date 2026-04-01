"""Tests for coverage format parsers."""

import json

import pytest

from repoforge.coverage.parsers import (
    parse_cobertura,
    parse_coverage_py_json,
    parse_jacoco,
    parse_lcov,
)


# ---------------------------------------------------------------------------
# Cobertura XML
# ---------------------------------------------------------------------------


COBERTURA_XML = """\
<?xml version="1.0" ?>
<coverage version="5.5" timestamp="1234567890" lines-valid="100" lines-covered="80"
          line-rate="0.8" branches-covered="6" branches-valid="10" branch-rate="0.6">
  <packages>
    <package name="myapp" line-rate="0.8" branch-rate="0.6">
      <classes>
        <class name="main.py" filename="myapp/main.py" line-rate="0.9" branch-rate="0.75">
          <lines>
            <line number="1" hits="1"/>
            <line number="2" hits="1"/>
            <line number="3" hits="0"/>
            <line number="4" hits="1"/>
            <line number="5" hits="1" branch="true" condition-coverage="75% (3/4)"/>
          </lines>
        </class>
        <class name="utils.py" filename="myapp/utils.py" line-rate="0.7" branch-rate="0.5">
          <lines>
            <line number="1" hits="1"/>
            <line number="2" hits="0"/>
            <line number="3" hits="1"/>
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
"""


class TestParseCobertura:

    def test_parses_files(self, tmp_path):
        p = tmp_path / "coverage.xml"
        p.write_text(COBERTURA_XML)
        report = parse_cobertura(p)

        assert report.source_format == "cobertura"
        assert len(report.files) == 2

    def test_file_paths(self, tmp_path):
        p = tmp_path / "coverage.xml"
        p.write_text(COBERTURA_XML)
        report = parse_cobertura(p)

        paths = {f.path for f in report.files}
        assert "myapp/main.py" in paths
        assert "myapp/utils.py" in paths

    def test_line_rates(self, tmp_path):
        p = tmp_path / "coverage.xml"
        p.write_text(COBERTURA_XML)
        report = parse_cobertura(p)

        main = next(f for f in report.files if f.path == "myapp/main.py")
        assert main.line_rate == 0.9
        assert main.lines_covered == 4
        assert main.lines_total == 5

    def test_branch_coverage(self, tmp_path):
        p = tmp_path / "coverage.xml"
        p.write_text(COBERTURA_XML)
        report = parse_cobertura(p)

        main = next(f for f in report.files if f.path == "myapp/main.py")
        assert main.branches_covered == 3
        assert main.branches_total == 4

    def test_empty_package(self, tmp_path):
        xml = '<?xml version="1.0" ?><coverage><packages><package name="empty"><classes></classes></package></packages></coverage>'
        p = tmp_path / "cov.xml"
        p.write_text(xml)
        report = parse_cobertura(p)
        assert len(report.files) == 0


# ---------------------------------------------------------------------------
# lcov
# ---------------------------------------------------------------------------


LCOV_DATA = """\
TN:
SF:src/app.ts
FNF:5
FNH:4
DA:1,1
DA:2,1
DA:3,0
DA:4,1
LF:4
LH:3
BRF:6
BRH:4
end_of_record
SF:src/utils.ts
FNF:3
FNH:3
DA:1,1
DA:2,1
LF:2
LH:2
BRF:0
BRH:0
end_of_record
"""


class TestParseLcov:

    def test_parses_files(self, tmp_path):
        p = tmp_path / "lcov.info"
        p.write_text(LCOV_DATA)
        report = parse_lcov(p)

        assert report.source_format == "lcov"
        assert len(report.files) == 2

    def test_file_paths(self, tmp_path):
        p = tmp_path / "lcov.info"
        p.write_text(LCOV_DATA)
        report = parse_lcov(p)

        paths = [f.path for f in report.files]
        assert "src/app.ts" in paths
        assert "src/utils.ts" in paths

    def test_line_coverage(self, tmp_path):
        p = tmp_path / "lcov.info"
        p.write_text(LCOV_DATA)
        report = parse_lcov(p)

        app = next(f for f in report.files if f.path == "src/app.ts")
        assert app.lines_covered == 3
        assert app.lines_total == 4
        assert app.line_rate == 0.75

    def test_branch_coverage(self, tmp_path):
        p = tmp_path / "lcov.info"
        p.write_text(LCOV_DATA)
        report = parse_lcov(p)

        app = next(f for f in report.files if f.path == "src/app.ts")
        assert app.branches_covered == 4
        assert app.branches_total == 6

    def test_function_coverage(self, tmp_path):
        p = tmp_path / "lcov.info"
        p.write_text(LCOV_DATA)
        report = parse_lcov(p)

        app = next(f for f in report.files if f.path == "src/app.ts")
        assert app.functions_covered == 4
        assert app.functions_total == 5
        assert app.function_rate == 0.8

    def test_no_branches_returns_none(self, tmp_path):
        p = tmp_path / "lcov.info"
        p.write_text(LCOV_DATA)
        report = parse_lcov(p)

        utils = next(f for f in report.files if f.path == "src/utils.ts")
        assert utils.branch_rate is None

    def test_empty_file(self, tmp_path):
        p = tmp_path / "lcov.info"
        p.write_text("")
        report = parse_lcov(p)
        assert len(report.files) == 0


# ---------------------------------------------------------------------------
# coverage.py JSON
# ---------------------------------------------------------------------------


COVERAGE_PY_JSON = {
    "meta": {"version": "7.0", "timestamp": "2024-01-01"},
    "files": {
        "myapp/main.py": {
            "executed_lines": [1, 2, 3, 5, 6],
            "missing_lines": [4, 7],
            "summary": {
                "covered_lines": 5,
                "missing_lines": 2,
                "percent_covered": 71.42857,
                "covered_branches": 3,
                "missing_branches": 1,
            },
        },
        "myapp/utils.py": {
            "executed_lines": [1, 2, 3],
            "missing_lines": [],
            "summary": {
                "covered_lines": 3,
                "missing_lines": 0,
                "percent_covered": 100.0,
            },
        },
    },
    "totals": {"percent_covered": 85.7},
}


class TestParseCoveragePyJson:

    def test_parses_files(self, tmp_path):
        p = tmp_path / "coverage.json"
        p.write_text(json.dumps(COVERAGE_PY_JSON))
        report = parse_coverage_py_json(p)

        assert report.source_format == "coverage_py"
        assert len(report.files) == 2

    def test_line_coverage(self, tmp_path):
        p = tmp_path / "coverage.json"
        p.write_text(json.dumps(COVERAGE_PY_JSON))
        report = parse_coverage_py_json(p)

        main = next(f for f in report.files if f.path == "myapp/main.py")
        assert main.lines_covered == 5
        assert main.lines_total == 7
        assert abs(main.line_rate - 0.7142857) < 0.001

    def test_branch_coverage(self, tmp_path):
        p = tmp_path / "coverage.json"
        p.write_text(json.dumps(COVERAGE_PY_JSON))
        report = parse_coverage_py_json(p)

        main = next(f for f in report.files if f.path == "myapp/main.py")
        assert main.branches_covered == 3
        assert main.branches_total == 4

    def test_no_branches(self, tmp_path):
        p = tmp_path / "coverage.json"
        p.write_text(json.dumps(COVERAGE_PY_JSON))
        report = parse_coverage_py_json(p)

        utils = next(f for f in report.files if f.path == "myapp/utils.py")
        assert utils.branch_rate is None

    def test_full_coverage_rate(self, tmp_path):
        p = tmp_path / "coverage.json"
        p.write_text(json.dumps(COVERAGE_PY_JSON))
        report = parse_coverage_py_json(p)

        utils = next(f for f in report.files if f.path == "myapp/utils.py")
        assert utils.line_rate == 1.0


# ---------------------------------------------------------------------------
# JaCoCo XML
# ---------------------------------------------------------------------------


JACOCO_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd">
<report name="my-project">
  <package name="com/example/app">
    <sourcefile name="Main.java">
      <counter type="LINE" missed="10" covered="90"/>
      <counter type="BRANCH" missed="4" covered="12"/>
      <counter type="METHOD" missed="1" covered="9"/>
    </sourcefile>
    <sourcefile name="Utils.java">
      <counter type="LINE" missed="0" covered="50"/>
      <counter type="METHOD" missed="0" covered="5"/>
    </sourcefile>
  </package>
</report>
"""


class TestParseJacoco:

    def test_parses_files(self, tmp_path):
        p = tmp_path / "jacoco.xml"
        p.write_text(JACOCO_XML)
        report = parse_jacoco(p)

        assert report.source_format == "jacoco"
        assert len(report.files) == 2

    def test_file_paths(self, tmp_path):
        p = tmp_path / "jacoco.xml"
        p.write_text(JACOCO_XML)
        report = parse_jacoco(p)

        paths = {f.path for f in report.files}
        assert "com/example/app/Main.java" in paths
        assert "com/example/app/Utils.java" in paths

    def test_line_coverage(self, tmp_path):
        p = tmp_path / "jacoco.xml"
        p.write_text(JACOCO_XML)
        report = parse_jacoco(p)

        main = next(f for f in report.files if "Main.java" in f.path)
        assert main.lines_covered == 90
        assert main.lines_total == 100
        assert main.line_rate == 0.9

    def test_branch_coverage(self, tmp_path):
        p = tmp_path / "jacoco.xml"
        p.write_text(JACOCO_XML)
        report = parse_jacoco(p)

        main = next(f for f in report.files if "Main.java" in f.path)
        assert main.branches_covered == 12
        assert main.branches_total == 16
        assert main.branch_rate == 0.75

    def test_method_coverage(self, tmp_path):
        p = tmp_path / "jacoco.xml"
        p.write_text(JACOCO_XML)
        report = parse_jacoco(p)

        main = next(f for f in report.files if "Main.java" in f.path)
        assert main.functions_covered == 9
        assert main.functions_total == 10
        assert main.function_rate == 0.9

    def test_no_branch_counter(self, tmp_path):
        p = tmp_path / "jacoco.xml"
        p.write_text(JACOCO_XML)
        report = parse_jacoco(p)

        utils = next(f for f in report.files if "Utils.java" in f.path)
        assert utils.branch_rate is None

    def test_full_line_coverage(self, tmp_path):
        p = tmp_path / "jacoco.xml"
        p.write_text(JACOCO_XML)
        report = parse_jacoco(p)

        utils = next(f for f in report.files if "Utils.java" in f.path)
        assert utils.line_rate == 1.0
        assert utils.lines_covered == 50
