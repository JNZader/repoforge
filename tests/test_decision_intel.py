"""Tests for decision_intel — WHY/DECISION/TRADEOFF extraction from code."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from repoforge.decision_intel import (
    Decision,
    DecisionReport,
    extract_decisions_from_content,
    scan_directory,
)

# ── extract_decisions_from_content ──


class TestExtractDecisions:
    def test_extracts_why_comment(self):
        content = "x = 1\n// WHY: performance optimization\ny = 2"
        decisions = extract_decisions_from_content(content, "app.ts")
        assert len(decisions) == 1
        assert decisions[0].marker == "WHY"
        assert decisions[0].text == "performance optimization"
        assert decisions[0].line == 2

    def test_extracts_decision_comment(self):
        content = "# DECISION: use PostgreSQL over MySQL for JSONB support"
        decisions = extract_decisions_from_content(content, "config.py")
        assert len(decisions) == 1
        assert decisions[0].marker == "DECISION"
        assert "PostgreSQL" in decisions[0].text

    def test_extracts_tradeoff_comment(self):
        content = "// TRADEOFF: slower writes but faster reads with this index"
        decisions = extract_decisions_from_content(content, "db.ts")
        assert len(decisions) == 1
        assert decisions[0].marker == "TRADEOFF"

    def test_extracts_hack_comment(self):
        content = "# HACK: workaround for upstream bug #123"
        decisions = extract_decisions_from_content(content, "fix.py")
        assert len(decisions) == 1
        assert decisions[0].marker == "HACK"

    def test_extracts_note_comment(self):
        content = "// NOTE: this will be deprecated in v2"
        decisions = extract_decisions_from_content(content, "legacy.ts")
        assert len(decisions) == 1
        assert decisions[0].marker == "NOTE"

    def test_extracts_block_comment(self):
        content = "/* DECISION: use JWT over sessions for statelessness */"
        decisions = extract_decisions_from_content(content, "auth.java")
        assert len(decisions) == 1
        assert decisions[0].marker == "DECISION"

    def test_extracts_star_comment_line(self):
        content = " * WHY: reduces coupling between modules"
        decisions = extract_decisions_from_content(content, "arch.ts")
        assert len(decisions) == 1

    def test_case_insensitive(self):
        content = "// why: lowercase works too"
        decisions = extract_decisions_from_content(content, "test.ts")
        assert len(decisions) == 1
        assert decisions[0].marker == "WHY"

    def test_multiple_decisions_in_one_file(self):
        content = "\n".join([
            "// WHY: reason one",
            "code()",
            "# DECISION: reason two",
            "more_code()",
            "// TRADEOFF: reason three",
        ])
        decisions = extract_decisions_from_content(content, "multi.py")
        assert len(decisions) == 3
        assert decisions[0].line == 1
        assert decisions[1].line == 3
        assert decisions[2].line == 5

    def test_no_decisions_in_clean_code(self):
        content = "const x = 1;\nconst y = 2;\nconsole.log(x + y);"
        decisions = extract_decisions_from_content(content, "clean.ts")
        assert len(decisions) == 0

    def test_ignores_false_positives(self):
        content = 'const WHY = "not a decision";'
        decisions = extract_decisions_from_content(content, "false.ts")
        assert len(decisions) == 0

    def test_context_lines(self):
        content = "line1\nline2\n// WHY: important\nline4\nline5"
        decisions = extract_decisions_from_content(content, "ctx.ts", context_lines=1)
        assert "line2" in decisions[0].context
        assert "line4" in decisions[0].context

    def test_file_path_preserved(self):
        decisions = extract_decisions_from_content(
            "// WHY: important architectural reason", "src/deep/file.ts"
        )
        assert decisions[0].file == "src/deep/file.ts"


# ── scan_directory ──


class TestScanDirectory:
    def test_scans_python_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "app.py").write_text("# WHY: testing\nx = 1\n")
            decisions = scan_directory(p)
            assert len(decisions) == 1
            assert decisions[0].marker == "WHY"

    def test_scans_typescript_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "app.ts").write_text("// DECISION: use signals\n")
            decisions = scan_directory(p)
            assert len(decisions) == 1

    def test_skips_node_modules(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            nm = p / "node_modules" / "pkg"
            nm.mkdir(parents=True)
            (nm / "index.js").write_text("// WHY: should be skipped\n")
            (p / "app.py").write_text("# WHY: should be found\n")
            decisions = scan_directory(p)
            assert len(decisions) == 1
            assert "app.py" in decisions[0].file

    def test_handles_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            decisions = scan_directory(Path(tmpdir))
            assert len(decisions) == 0

    def test_recursive_scan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            sub = p / "src" / "utils"
            sub.mkdir(parents=True)
            (sub / "helper.py").write_text("# TRADEOFF: speed vs memory\n")
            decisions = scan_directory(p)
            assert len(decisions) == 1

    def test_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "a.py").write_text("# WHY: reason a\n")
            (p / "b.ts").write_text("// DECISION: reason b\n")
            (p / "c.go").write_text("// HACK: reason c\n")
            decisions = scan_directory(p)
            assert len(decisions) == 3


# ── DecisionReport ──


class TestDecisionReport:
    def _build_report(self) -> DecisionReport:
        report = DecisionReport()
        report.decisions = [
            Decision("WHY", "reason one", "app.ts", 10),
            Decision("DECISION", "reason two", "app.ts", 20),
            Decision("WHY", "reason three", "db.ts", 5),
            Decision("TRADEOFF", "reason four", "config.py", 1),
        ]
        return report

    def test_by_marker(self):
        report = self._build_report()
        by_marker = report.by_marker
        assert len(by_marker["WHY"]) == 2
        assert len(by_marker["DECISION"]) == 1
        assert len(by_marker["TRADEOFF"]) == 1

    def test_by_file(self):
        report = self._build_report()
        by_file = report.by_file
        assert len(by_file["app.ts"]) == 2
        assert len(by_file["db.ts"]) == 1

    def test_summary(self):
        report = self._build_report()
        summary = report.summary()
        assert summary == {"WHY": 2, "DECISION": 1, "TRADEOFF": 1}

    def test_to_markdown(self):
        report = self._build_report()
        md = report.to_markdown()
        assert "# Decision Intelligence Report" in md
        assert "## WHY (2)" in md
        assert "## DECISION (1)" in md
        assert "app.ts:10" in md

    def test_empty_report_markdown(self):
        report = DecisionReport()
        assert "No decisions found" in report.to_markdown()

    def test_to_dict_roundtrip(self):
        report = self._build_report()
        data = report.to_dict()
        restored = DecisionReport.from_dict(data)
        assert len(restored.decisions) == len(report.decisions)
        for orig, rest in zip(report.decisions, restored.decisions):
            assert orig.marker == rest.marker
            assert orig.text == rest.text
            assert orig.file == rest.file
            assert orig.line == rest.line

    def test_to_dict_is_json_serializable(self):
        report = self._build_report()
        json_str = json.dumps(report.to_dict())
        assert json_str
