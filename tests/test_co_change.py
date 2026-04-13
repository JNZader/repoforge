"""Tests for co_change module — item #17."""

import subprocess
from pathlib import Path

import pytest

from repoforge.co_change import (
    CoChangePair,
    CoChangeReport,
    _is_code_file,
    detect_co_changes,
    format_co_changes,
)

# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestIsCodeFile:
    def test_python_file(self):
        assert _is_code_file("src/main.py") is True

    def test_typescript_file(self):
        assert _is_code_file("src/app.ts") is True

    def test_markdown_excluded(self):
        assert _is_code_file("README.md") is False

    def test_lock_file_excluded(self):
        assert _is_code_file("package-lock.json") is False

    def test_yaml_excluded(self):
        assert _is_code_file("config.yaml") is False

    def test_image_excluded(self):
        assert _is_code_file("logo.png") is False

    def test_go_file(self):
        assert _is_code_file("cmd/main.go") is True


class TestCoChangePair:
    def test_confidence_high(self):
        p = CoChangePair("a.py", "b.py", 10, 10, 10, 0.9)
        assert p.confidence == "high"

    def test_confidence_medium(self):
        p = CoChangePair("a.py", "b.py", 5, 10, 10, 0.6)
        assert p.confidence == "medium"

    def test_confidence_low(self):
        p = CoChangePair("a.py", "b.py", 3, 10, 10, 0.3)
        assert p.confidence == "low"


class TestCoChangeReport:
    def test_hidden_coupling(self):
        report = CoChangeReport(pairs=[
            CoChangePair("a.py", "b.py", 5, 5, 5, 0.8, has_import_link=True),
            CoChangePair("c.py", "d.py", 4, 5, 5, 0.7, has_import_link=False),
        ])
        hidden = report.hidden_coupling
        assert len(hidden) == 1
        assert hidden[0].file_a == "c.py"


# ---------------------------------------------------------------------------
# Integration with git repo
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo_with_history(tmp_path):
    """Create a git repo with co-change patterns."""
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"],
                   cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"],
                   cwd=str(repo), capture_output=True)

    # Create files
    (repo / "a.py").write_text("# a\n")
    (repo / "b.py").write_text("# b\n")
    (repo / "c.py").write_text("# c\n")

    # Commit 1: a + b change together
    subprocess.run(["git", "add", "a.py", "b.py", "c.py"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True)

    # Commits 2-5: a + b always together
    for i in range(4):
        (repo / "a.py").write_text(f"# a v{i}\n")
        (repo / "b.py").write_text(f"# b v{i}\n")
        subprocess.run(["git", "add", "a.py", "b.py"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", f"update {i}"],
                       cwd=str(repo), capture_output=True)

    # Commit 6: only c changes
    (repo / "c.py").write_text("# c v2\n")
    subprocess.run(["git", "add", "c.py"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "commit", "-m", "update c"], cwd=str(repo), capture_output=True)

    return repo


class TestDetectCoChanges:
    def test_finds_co_change_pair(self, git_repo_with_history):
        report = detect_co_changes(
            str(git_repo_with_history),
            threshold=0.3,
            min_commits=3,
            check_imports=False,
        )
        assert report.commits_analyzed > 0
        # a.py and b.py should appear as co-change pair
        pairs_files = [(p.file_a, p.file_b) for p in report.pairs]
        assert ("a.py", "b.py") in pairs_files or ("b.py", "a.py") in pairs_files

    def test_empty_repo(self, tmp_path):
        repo = tmp_path / "empty"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)

        report = detect_co_changes(str(repo), check_imports=False)
        assert report.commits_analyzed == 0
        assert report.pairs == []


class TestFormatCoChanges:
    def test_format_empty(self):
        report = CoChangeReport()
        text = format_co_changes(report)
        assert "Co-Change" in text
        assert "No co-change pairs" in text

    def test_format_with_data(self):
        report = CoChangeReport(
            pairs=[
                CoChangePair("a.py", "b.py", 5, 5, 5, 0.8, has_import_link=False),
            ],
            commits_analyzed=100,
            files_analyzed=10,
        )
        text = format_co_changes(report)
        assert "a.py" in text
        assert "b.py" in text
        assert "Hidden Coupling" in text
