"""Tests for ownership module — item #18."""

import subprocess
from pathlib import Path

import pytest

from repoforge.ownership import (
    DirectoryOwnership,
    FileOwnership,
    OwnershipReport,
    analyze_ownership,
    format_ownership,
)

# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestFileOwnership:
    def test_top_contributor(self):
        fo = FileOwnership(
            file="a.py",
            contributors={"alice": 10, "bob": 3},
            total_commits=13,
        )
        assert fo.top_contributor == "alice"

    def test_ownership_ratio(self):
        fo = FileOwnership(
            file="a.py",
            contributors={"alice": 8, "bob": 2},
            total_commits=10,
        )
        assert fo.ownership_ratio == 0.8

    def test_bus_factor_single_author(self):
        fo = FileOwnership(
            file="a.py",
            contributors={"alice": 10},
            total_commits=10,
        )
        assert fo.bus_factor == 1
        assert fo.risk_level == "critical"

    def test_bus_factor_two_authors(self):
        fo = FileOwnership(
            file="a.py",
            contributors={"alice": 5, "bob": 5},
            total_commits=10,
        )
        assert fo.bus_factor == 1  # either one covers 50%
        assert fo.risk_level == "critical"

    def test_bus_factor_balanced(self):
        fo = FileOwnership(
            file="a.py",
            contributors={"alice": 4, "bob": 3, "carol": 3},
            total_commits=10,
        )
        assert fo.bus_factor == 2  # alice(4) + bob(3) = 7 >= 5
        assert fo.risk_level == "warning"

    def test_empty_contributors(self):
        fo = FileOwnership(file="a.py")
        assert fo.top_contributor is None
        assert fo.ownership_ratio == 0.0
        assert fo.bus_factor == 0


class TestDirectoryOwnership:
    def test_basic(self):
        do = DirectoryOwnership(
            directory="src",
            contributors={"alice": 20, "bob": 5},
            file_count=3,
            total_commits=25,
        )
        assert do.top_contributor == "alice"
        assert do.ownership_ratio == 0.8
        assert do.bus_factor == 1


class TestOwnershipReport:
    def test_bus_factor_risks(self):
        report = OwnershipReport(
            files=[
                FileOwnership("a.py", {"alice": 10}, 10),
                FileOwnership("b.py", {"alice": 5, "bob": 5, "carol": 5}, 15),
            ],
        )
        risks = report.bus_factor_risks
        assert len(risks) == 1
        assert risks[0].file == "a.py"


# ---------------------------------------------------------------------------
# Integration with git repo
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo_multi_author(tmp_path):
    """Create a git repo with multiple authors."""
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)

    # Alice's commits
    subprocess.run(["git", "config", "user.email", "alice@test.com"],
                   cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alice"],
                   cwd=str(repo), capture_output=True)

    (repo / "core.py").write_text("# core by alice\n")
    (repo / "utils.py").write_text("# utils by alice\n")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init by alice"],
                   cwd=str(repo), capture_output=True)

    for i in range(3):
        (repo / "core.py").write_text(f"# core v{i}\n")
        subprocess.run(["git", "add", "core.py"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", f"alice update {i}"],
                       cwd=str(repo), capture_output=True)

    # Bob's commits
    subprocess.run(["git", "config", "user.name", "Bob"],
                   cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.email", "bob@test.com"],
                   cwd=str(repo), capture_output=True)

    (repo / "utils.py").write_text("# utils by bob\n")
    subprocess.run(["git", "add", "utils.py"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "commit", "-m", "bob update utils"],
                   cwd=str(repo), capture_output=True)

    return repo


class TestAnalyzeOwnership:
    def test_finds_authors(self, git_repo_multi_author):
        report = analyze_ownership(str(git_repo_multi_author))
        assert report.total_contributors >= 2
        assert report.total_files >= 2

        # core.py should be mostly Alice's
        core = next((f for f in report.files if f.file == "core.py"), None)
        assert core is not None
        assert core.top_contributor == "Alice"

    def test_empty_repo(self, tmp_path):
        repo = tmp_path / "empty"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)

        report = analyze_ownership(str(repo))
        assert report.total_files == 0


class TestFormatOwnership:
    def test_format_basic(self):
        report = OwnershipReport(
            files=[
                FileOwnership("a.py", {"alice": 10}, 10),
            ],
            directories=[
                DirectoryOwnership("(root)", {"alice": 10}, 1, 10),
            ],
            total_contributors=1,
            total_files=1,
        )
        text = format_ownership(report)
        assert "Ownership" in text
        assert "alice" in text

    def test_format_with_bus_factor(self):
        report = OwnershipReport(
            files=[
                FileOwnership("a.py", {"alice": 10}, 10),
            ],
            directories=[],
            total_contributors=1,
            total_files=1,
        )
        text = format_ownership(report, bus_factor=True)
        assert "Bus Factor" in text
