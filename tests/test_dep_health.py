"""
tests/test_dep_health.py — Tests for dependency health analysis.

Tests cover:
- Node.js ecosystem (package.json, package-lock.json v1 and v2)
- Python ecosystem (pyproject.toml, requirements.txt, uv.lock)
- Duplicate detection
- License conflict detection
- Outdated dependency hints
- Health score classification
- Markdown report rendering
- Edge cases (missing files, malformed JSON, empty repos)
"""

import json
from pathlib import Path

import pytest

from repoforge.dep_health import (
    DependencyHealthReport,
    DuplicateDep,
    LicenseConflict,
    OutdatedDep,
    analyze_dependency_health,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def node_repo(tmp_path: Path) -> Path:
    """Create a minimal Node.js repo with package.json and lock file."""
    pkg = {
        "name": "test-project",
        "version": "1.0.0",
        "license": "MIT",
        "dependencies": {
            "express": "^4.18.0",
            "lodash": "^4.17.21",
        },
        "devDependencies": {
            "jest": "^29.0.0",
        },
    }
    (tmp_path / "package.json").write_text(json.dumps(pkg))

    lock = {
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "test-project", "version": "1.0.0"},
            "node_modules/express": {"version": "4.18.2"},
            "node_modules/express/node_modules/debug": {"version": "2.6.9"},
            "node_modules/express/node_modules/debug/node_modules/ms": {"version": "2.0.0"},
            "node_modules/lodash": {"version": "4.17.21"},
            "node_modules/ms": {"version": "2.1.3"},
            "node_modules/jest": {"version": "29.7.0"},
            "node_modules/debug": {"version": "4.3.4"},
        },
    }
    (tmp_path / "package-lock.json").write_text(json.dumps(lock))
    return tmp_path


@pytest.fixture
def node_repo_v1_lock(tmp_path: Path) -> Path:
    """Node.js repo with lockfileVersion 1."""
    pkg = {
        "name": "legacy-project",
        "version": "1.0.0",
        "dependencies": {"express": "^4.0.0"},
    }
    (tmp_path / "package.json").write_text(json.dumps(pkg))

    lock = {
        "lockfileVersion": 1,
        "dependencies": {
            "express": {
                "version": "4.18.2",
                "dependencies": {
                    "debug": {
                        "version": "2.6.9",
                        "dependencies": {
                            "ms": {"version": "2.0.0"},
                        },
                    },
                },
            },
            "debug": {"version": "4.3.4"},
            "ms": {"version": "2.1.3"},
        },
    }
    (tmp_path / "package-lock.json").write_text(json.dumps(lock))
    return tmp_path


@pytest.fixture
def python_repo(tmp_path: Path) -> Path:
    """Create a minimal Python repo with pyproject.toml."""
    pyproject = """\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "my-lib"
version = "1.0.0"
dependencies = [
    "click>=8.1.0",
    "pyyaml>=6.0",
    "requests>=2.28.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
]
"""
    (tmp_path / "pyproject.toml").write_text(pyproject)
    return tmp_path


@pytest.fixture
def python_repo_with_req(tmp_path: Path) -> Path:
    """Python repo with requirements.txt only."""
    req = """\
# Core
flask>=2.0.0
sqlalchemy>=2.0
redis==0.1.0
# Dev
-e .
"""
    (tmp_path / "requirements.txt").write_text(req)
    return tmp_path


@pytest.fixture
def python_repo_with_uv_lock(tmp_path: Path) -> Path:
    """Python repo with pyproject.toml + uv.lock."""
    pyproject = """\
[project]
name = "my-lib"
version = "1.0.0"
dependencies = [
    "click>=8.1.0",
]
"""
    (tmp_path / "pyproject.toml").write_text(pyproject)

    uv_lock = """\
[[package]]
name = "click"
version = "8.1.7"

[[package]]
name = "colorama"
version = "0.4.6"

[[package]]
name = "certifi"
version = "2024.2.2"
"""
    (tmp_path / "uv.lock").write_text(uv_lock)
    return tmp_path


# ---------------------------------------------------------------------------
# Node.js tests
# ---------------------------------------------------------------------------

class TestNodeAnalysis:
    def test_detects_node_ecosystem(self, node_repo: Path):
        report = analyze_dependency_health(str(node_repo))
        assert report is not None
        assert report.ecosystem == "node"

    def test_counts_direct_deps(self, node_repo: Path):
        report = analyze_dependency_health(str(node_repo))
        assert report.direct_count == 3  # express + lodash + jest

    def test_counts_transitive_deps(self, node_repo: Path):
        report = analyze_dependency_health(str(node_repo))
        # 5 unique packages: express, debug, ms, lodash, jest
        assert report.transitive_count == 5

    def test_calculates_tree_depth(self, node_repo: Path):
        report = analyze_dependency_health(str(node_repo))
        # express -> debug -> ms = depth 3
        assert report.max_tree_depth == 3

    def test_detects_duplicates(self, node_repo: Path):
        report = analyze_dependency_health(str(node_repo))
        dup_names = {d.name for d in report.duplicates}
        # debug appears at depth 1 and nested under express
        assert "debug" in dup_names
        # ms appears at depth 1 and nested under debug
        assert "ms" in dup_names

    def test_lockfile_v1(self, node_repo_v1_lock: Path):
        report = analyze_dependency_health(str(node_repo_v1_lock))
        assert report.ecosystem == "node"
        assert report.transitive_count >= 3
        assert report.max_tree_depth >= 3

    def test_lockfile_v1_duplicates(self, node_repo_v1_lock: Path):
        report = analyze_dependency_health(str(node_repo_v1_lock))
        dup_names = {d.name for d in report.duplicates}
        assert "debug" in dup_names

    def test_no_lock_file(self, tmp_path: Path):
        pkg = {"name": "no-lock", "dependencies": {"express": "^4.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        report = analyze_dependency_health(str(tmp_path))
        assert report is not None
        assert any("lock" in w.lower() for w in report.warnings)


class TestNodeLicenses:
    def test_detects_copyleft_license(self, node_repo: Path):
        """Create a dep with GPL license and verify detection."""
        nm = node_repo / "node_modules" / "express"
        nm.mkdir(parents=True, exist_ok=True)
        dep_pkg = {"name": "express", "license": "GPL-3.0"}
        (nm / "package.json").write_text(json.dumps(dep_pkg))

        report = analyze_dependency_health(str(node_repo))
        conflict_pkgs = {lc.package for lc in report.license_conflicts}
        assert "express" in conflict_pkgs

    def test_no_conflict_for_mit(self, node_repo: Path):
        nm = node_repo / "node_modules" / "express"
        nm.mkdir(parents=True, exist_ok=True)
        dep_pkg = {"name": "express", "license": "MIT"}
        (nm / "package.json").write_text(json.dumps(dep_pkg))

        report = analyze_dependency_health(str(node_repo))
        assert len(report.license_conflicts) == 0


class TestNodeOutdated:
    def test_flags_zero_major(self, tmp_path: Path):
        pkg = {
            "name": "test",
            "dependencies": {"old-lib": "^0.3.2", "new-lib": "^2.0.0"},
        }
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        report = analyze_dependency_health(str(tmp_path))
        outdated_names = {o.name for o in report.outdated_hints}
        assert "old-lib" in outdated_names
        assert "new-lib" not in outdated_names


# ---------------------------------------------------------------------------
# Python tests
# ---------------------------------------------------------------------------

class TestPythonAnalysis:
    def test_detects_python_ecosystem(self, python_repo: Path):
        report = analyze_dependency_health(str(python_repo))
        assert report is not None
        assert report.ecosystem == "python"

    def test_counts_direct_deps(self, python_repo: Path):
        report = analyze_dependency_health(str(python_repo))
        assert report.direct_count == 3  # click, pyyaml, requests

    def test_requirements_txt(self, python_repo_with_req: Path):
        report = analyze_dependency_health(str(python_repo_with_req))
        assert report.ecosystem == "python"
        assert report.direct_count == 3  # flask, sqlalchemy, redis

    def test_flags_outdated_python(self, python_repo_with_req: Path):
        report = analyze_dependency_health(str(python_repo_with_req))
        outdated_names = {o.name for o in report.outdated_hints}
        assert "redis" in outdated_names

    def test_uv_lock_transitive(self, python_repo_with_uv_lock: Path):
        report = analyze_dependency_health(str(python_repo_with_uv_lock))
        assert report.transitive_count == 3  # click, colorama, certifi

    def test_no_lock_warning(self, python_repo: Path):
        report = analyze_dependency_health(str(python_repo))
        assert any("lock" in w.lower() for w in report.warnings)


# ---------------------------------------------------------------------------
# Health score tests
# ---------------------------------------------------------------------------

class TestHealthScore:
    def test_good_health(self):
        report = DependencyHealthReport(
            ecosystem="node", direct_count=5, transitive_count=20,
            max_tree_depth=3,
        )
        assert report.health_score == "good"

    def test_moderate_health(self):
        report = DependencyHealthReport(
            ecosystem="node", direct_count=50, transitive_count=200,
            max_tree_depth=6,
            duplicates=[DuplicateDep(name="x", versions=["1.0", "2.0"])],
        )
        assert report.health_score == "moderate"

    def test_poor_health(self):
        report = DependencyHealthReport(
            ecosystem="node", direct_count=100, transitive_count=500,
            max_tree_depth=10,
            duplicates=[
                DuplicateDep(name=f"pkg-{i}", versions=["1.0", "2.0"])
                for i in range(5)
            ],
        )
        assert report.health_score == "poor"


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

class TestMarkdownReport:
    def test_renders_summary_table(self):
        report = DependencyHealthReport(
            ecosystem="node", direct_count=10, transitive_count=50,
            max_tree_depth=4,
        )
        md = report.to_markdown()
        assert "## Dependency Health" in md
        assert "| Direct dependencies | 10 |" in md
        assert "| Transitive dependencies | 50 |" in md
        assert "**good**" in md

    def test_renders_duplicates(self):
        report = DependencyHealthReport(
            ecosystem="node",
            duplicates=[DuplicateDep(name="lodash", versions=["3.0.0", "4.17.21"])],
        )
        md = report.to_markdown()
        assert "### Duplicate Dependencies" in md
        assert "`lodash`" in md

    def test_renders_license_conflicts(self):
        report = DependencyHealthReport(
            ecosystem="node",
            license_conflicts=[LicenseConflict(
                package="gpl-lib", license="GPL-3.0", reason="Copyleft",
            )],
        )
        md = report.to_markdown()
        assert "### License Conflicts" in md
        assert "`gpl-lib`" in md

    def test_renders_warnings(self):
        report = DependencyHealthReport(
            ecosystem="python",
            warnings=["No lock file found"],
        )
        md = report.to_markdown()
        assert "### Warnings" in md
        assert "No lock file found" in md


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_repo_returns_none(self, tmp_path: Path):
        result = analyze_dependency_health(str(tmp_path))
        assert result is None

    def test_malformed_package_json(self, tmp_path: Path):
        (tmp_path / "package.json").write_text("{invalid json")
        report = analyze_dependency_health(str(tmp_path))
        assert report is not None
        assert any("parse" in w.lower() for w in report.warnings)

    def test_empty_package_json(self, tmp_path: Path):
        (tmp_path / "package.json").write_text("{}")
        report = analyze_dependency_health(str(tmp_path))
        assert report is not None
        assert report.direct_count == 0

    def test_malformed_lock(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(json.dumps({"name": "t"}))
        (tmp_path / "package-lock.json").write_text("not json")
        report = analyze_dependency_health(str(tmp_path))
        assert any("lock" in w.lower() for w in report.warnings)
