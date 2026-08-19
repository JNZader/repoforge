"""Tests for change_impact module — item #16."""

from pathlib import Path

import pytest

from repoforge.change_impact import (
    ChangeImpactReport,
    SourceTestMapping,
    _find_convention_tests,
    analyze_change_impact,
    format_change_impact,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_with_tests(tmp_path):
    """Create a temp project with source and test files."""
    # Source files
    (tmp_path / "auth.py").write_text(
        "def login(user, pwd): pass\n"
    )
    (tmp_path / "models.py").write_text(
        "class User: pass\n"
    )
    (tmp_path / "service.py").write_text(
        "from auth import login\nfrom models import User\n\ndef serve(): pass\n"
    )

    # Test files
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_auth.py").write_text(
        "from auth import login\ndef test_login(): pass\n"
    )
    (tests_dir / "test_service.py").write_text(
        "from service import serve\ndef test_serve(): pass\n"
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Unit tests: naming convention matching
# ---------------------------------------------------------------------------


class TestConventionMatching:
    def test_python_convention(self):
        all_files = {
            "auth.py", "tests/test_auth.py", "tests/test_models.py",
        }
        result = _find_convention_tests("auth.py", all_files)
        assert "tests/test_auth.py" in result

    def test_go_convention(self):
        all_files = {"pkg/handler.go", "pkg/handler_test.go"}
        result = _find_convention_tests("pkg/handler.go", all_files)
        assert "pkg/handler_test.go" in result

    def test_typescript_convention(self):
        all_files = {"src/auth.ts", "src/auth.test.ts", "src/auth.spec.ts"}
        result = _find_convention_tests("src/auth.ts", all_files)
        assert "src/auth.test.ts" in result
        assert "src/auth.spec.ts" in result

    def test_java_convention(self):
        all_files = {
            "src/main/Auth.java",
            "src/test/AuthTest.java",
        }
        result = _find_convention_tests("src/main/Auth.java", all_files)
        assert "src/test/AuthTest.java" in result

    def test_no_match(self):
        all_files = {"auth.py", "tests/test_models.py"}
        result = _find_convention_tests("auth.py", all_files)
        assert "tests/test_models.py" not in result


# ---------------------------------------------------------------------------
# Unit tests: report model
# ---------------------------------------------------------------------------


class TestChangeImpactReport:
    def test_all_tests_deduplication(self):
        report = ChangeImpactReport(
            changed_files=["a.py"],
            mappings=[
                SourceTestMapping(
                    source_file="a.py",
                    graph_tests=["test_a.py", "test_b.py"],
                    convention_tests=["test_a.py"],  # duplicate
                ),
            ],
        )
        assert report.all_tests == ["test_a.py", "test_b.py"]

    def test_untested_files(self):
        report = ChangeImpactReport(
            changed_files=["a.py", "b.py"],
            mappings=[
                SourceTestMapping(source_file="a.py", graph_tests=["test_a.py"]),
                SourceTestMapping(source_file="b.py"),  # no tests
            ],
        )
        assert report.untested_files == ["b.py"]

    def test_all_tests_unions_direct_and_derived_tests(self):
        report = ChangeImpactReport(
            changed_files=["auth.py", "tests/test_auth.py"],
            mappings=[
                SourceTestMapping(
                    source_file="auth.py",
                    graph_tests=["tests/test_service.py", "tests/test_auth.py"],
                ),
            ],
            direct_tests=["tests/test_auth.py"],
        )

        assert report.all_tests == ["tests/test_auth.py", "tests/test_service.py"]

    def test_existing_positional_constructor_order_is_compatible(self):
        mappings = [SourceTestMapping(source_file="auth.py")]

        report = ChangeImpactReport(["auth.py"], mappings, "abc123")

        assert report.changed_files == ["auth.py"]
        assert report.mappings is mappings
        assert report.commit == "abc123"


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


class TestAnalyzeChangeImpact:
    def test_with_file_list(self, project_with_tests):
        report = analyze_change_impact(
            str(project_with_tests),
            files=["auth.py"],
        )
        assert report.changed_files == ["auth.py"]
        assert len(report.mappings) == 1

    def test_empty_input(self, project_with_tests):
        report = analyze_change_impact(str(project_with_tests))
        assert report.all_tests == []

    @pytest.mark.parametrize("changed", [
        ["tests/test_service.py", "tests/test_auth.py"],
        ["tests/test_auth.py", "tests/test_service.py"],
    ])
    def test_direct_only_changes_preserve_input_and_sort_output(
        self, project_with_tests, changed,
    ):
        report = analyze_change_impact(str(project_with_tests), files=changed)

        assert report.changed_files == changed
        assert report.all_tests == ["tests/test_auth.py", "tests/test_service.py"]

    def test_mixed_changes_include_direct_and_source_derived_tests(
        self, project_with_tests,
    ):
        changed = ["tests/test_service.py", "auth.py"]

        report = analyze_change_impact(str(project_with_tests), files=changed)

        assert report.changed_files == changed
        assert report.all_tests == ["tests/test_auth.py", "tests/test_service.py"]
        assert [mapping.source_file for mapping in report.mappings] == ["auth.py"]

    @pytest.mark.parametrize("discovered", [False, True])
    def test_nonexistent_direct_test_is_reporting_only(self, project_with_tests,
        monkeypatch, discovered):
        changed = ["tests/test_deleted.py"]
        if discovered:
            monkeypatch.setattr("repoforge.change_impact._get_changed_files", lambda *_: changed)

        report = analyze_change_impact(
            str(project_with_tests), files=None if discovered else changed,
            commit="HEAD" if discovered else None,
        )

        assert report.changed_files == changed
        assert report.direct_tests == []
        assert report.all_tests == []

    def test_nonexistent_source_remains_in_impact_analysis(self, project_with_tests):
        changed = ["deleted.py"]

        report = analyze_change_impact(str(project_with_tests), files=changed)

        assert report.changed_files == changed
        assert [mapping.source_file for mapping in report.mappings] == changed

    def test_cli_json_excludes_nonexistent_direct_tests(self, project_with_tests):
        import json

        from click.testing import CliRunner

        from repoforge.cli import main

        changed = ["tests/test_service.py", "tests/test_deleted.py"]
        args = ["change-impact", "-w", str(project_with_tests), "--json", "--quiet"]
        for path in changed:
            args.extend(["--files", path])

        result = CliRunner().invoke(main, args)

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["changed_files"] == changed
        assert payload["tests_to_run"] == ["tests/test_service.py"]

class TestFormatChangeImpact:
    def test_format_basic(self):
        report = ChangeImpactReport(
            changed_files=["a.py"],
            mappings=[
                SourceTestMapping(
                    source_file="a.py",
                    graph_tests=["test_a.py"],
                ),
            ],
        )
        text = format_change_impact(report)
        assert "Change Impact" in text
        assert "test_a.py" in text

    def test_format_with_commit(self):
        report = ChangeImpactReport(
            changed_files=["a.py"],
            mappings=[],
            commit="abc123",
        )
        text = format_change_impact(report)
        assert "abc123" in text
