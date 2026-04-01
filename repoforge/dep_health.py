"""Dependency health analysis — tree depth, duplicates, outdated, license conflicts.

Deterministic analysis (no LLM) of project dependency health for Node.js
(package.json + package-lock.json) and Python (pyproject.toml + requirements.txt).

Produces a structured DependencyHealthReport consumed by the docs pipeline
to render a "Dependency Health" section in generated documentation.

Usage:
    from repoforge.dep_health import analyze_dependency_health
    report = analyze_dependency_health("/path/to/repo")
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DuplicateDep:
    """A dependency that appears with multiple versions."""
    name: str
    versions: list[str]


@dataclass
class LicenseConflict:
    """A dependency whose license may conflict with the project."""
    package: str
    license: str
    reason: str


@dataclass
class OutdatedDep:
    """A dependency that appears pinned to a very old version."""
    name: str
    current: str
    constraint: str  # the raw version constraint


@dataclass
class DependencyHealthReport:
    """Aggregated dependency health metrics for a project."""
    ecosystem: str  # "node", "python", or "unknown"
    direct_count: int = 0
    transitive_count: int = 0
    max_tree_depth: int = 0
    duplicates: list[DuplicateDep] = field(default_factory=list)
    license_conflicts: list[LicenseConflict] = field(default_factory=list)
    outdated_hints: list[OutdatedDep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def health_score(self) -> str:
        """Simple health classification: good, moderate, or poor."""
        issues = len(self.duplicates) + len(self.license_conflicts)
        if issues == 0 and self.max_tree_depth <= 5:
            return "good"
        if issues <= 3 and self.max_tree_depth <= 8:
            return "moderate"
        return "poor"

    def to_markdown(self) -> str:
        """Render report as a markdown section for documentation."""
        lines: list[str] = []
        lines.append("## Dependency Health\n")

        # Summary table
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Ecosystem | {self.ecosystem} |")
        lines.append(f"| Direct dependencies | {self.direct_count} |")
        lines.append(f"| Transitive dependencies | {self.transitive_count} |")
        lines.append(f"| Max tree depth | {self.max_tree_depth} |")
        lines.append(f"| Duplicates | {len(self.duplicates)} |")
        lines.append(f"| License conflicts | {len(self.license_conflicts)} |")
        lines.append(f"| Health | **{self.health_score}** |")
        lines.append("")

        # Duplicates
        if self.duplicates:
            lines.append("### Duplicate Dependencies\n")
            lines.append("| Package | Versions |")
            lines.append("|---------|----------|")
            for dup in self.duplicates[:20]:
                versions = ", ".join(dup.versions[:5])
                lines.append(f"| `{dup.name}` | {versions} |")
            lines.append("")

        # License conflicts
        if self.license_conflicts:
            lines.append("### License Conflicts\n")
            lines.append("| Package | License | Reason |")
            lines.append("|---------|---------|--------|")
            for lc in self.license_conflicts[:20]:
                lines.append(f"| `{lc.package}` | {lc.license} | {lc.reason} |")
            lines.append("")

        # Outdated hints
        if self.outdated_hints:
            lines.append("### Potentially Outdated\n")
            lines.append("| Package | Constraint |")
            lines.append("|---------|-----------|")
            for od in self.outdated_hints[:20]:
                lines.append(f"| `{od.name}` | {od.constraint} |")
            lines.append("")

        # Warnings
        if self.warnings:
            lines.append("### Warnings\n")
            for w in self.warnings:
                lines.append(f"- {w}")
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_dependency_health(repo_root: str) -> Optional[DependencyHealthReport]:
    """Analyze dependency health for a repository.

    Detects ecosystem (Node or Python) and parses manifest/lock files.
    Returns None if no supported manifest files are found.

    Args:
        repo_root: Path to the repository root.

    Returns:
        DependencyHealthReport or None if no manifest found.
    """
    root = Path(repo_root).resolve()

    # Try Node.js first (package.json)
    if (root / "package.json").exists():
        return _analyze_node(root)

    # Try Python (pyproject.toml or requirements.txt)
    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
        return _analyze_python(root)

    return None


# ---------------------------------------------------------------------------
# Node.js analysis
# ---------------------------------------------------------------------------

# Licenses commonly considered copyleft / restrictive
_COPYLEFT_LICENSES = {
    "GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0",
    "GPL-2.0-only", "GPL-3.0-only", "AGPL-3.0-only",
    "GPL-2.0-or-later", "GPL-3.0-or-later", "AGPL-3.0-or-later",
    "SSPL-1.0", "EUPL-1.2", "OSL-3.0", "CPAL-1.0",
}


def _analyze_node(root: Path) -> DependencyHealthReport:
    """Analyze Node.js dependency health from package.json + lock file."""
    report = DependencyHealthReport(ecosystem="node")

    # Parse package.json for direct deps
    try:
        pkg_data = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        report.warnings.append(f"Failed to parse package.json: {e}")
        return report

    deps = pkg_data.get("dependencies", {})
    dev_deps = pkg_data.get("devDependencies", {})
    report.direct_count = len(deps) + len(dev_deps)

    # Check for outdated pinning patterns in direct deps
    for name, constraint in {**deps, **dev_deps}.items():
        _check_outdated_node(name, constraint, report)

    # Parse lock file for transitive analysis
    lock_path = root / "package-lock.json"
    if lock_path.exists():
        _parse_node_lock(lock_path, report)
    else:
        report.warnings.append("No package-lock.json found — transitive analysis skipped")

    # License check from package.json metadata
    _check_node_licenses(root, pkg_data, report)

    return report


def _check_outdated_node(name: str, constraint: str, report: DependencyHealthReport) -> None:
    """Heuristic: flag deps pinned to major version 0.x or very old-looking constraints."""
    constraint = constraint.strip()
    # Match patterns like "0.1.2", "~0.3.4", "^0.5.0"
    match = re.match(r"^[~^]?0\.\d+\.\d+", constraint)
    if match:
        report.outdated_hints.append(OutdatedDep(
            name=name, current="0.x", constraint=constraint,
        ))


def _parse_node_lock(lock_path: Path, report: DependencyHealthReport) -> None:
    """Parse package-lock.json to extract transitive deps, depth, and duplicates."""
    try:
        lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        report.warnings.append(f"Failed to parse package-lock.json: {e}")
        return

    lock_version = lock_data.get("lockfileVersion", 1)

    if lock_version >= 2:
        _parse_node_lock_v2(lock_data, report)
    else:
        _parse_node_lock_v1(lock_data, report)


def _parse_node_lock_v2(lock_data: dict, report: DependencyHealthReport) -> None:
    """Parse lockfileVersion 2/3 (packages key with nested paths)."""
    packages = lock_data.get("packages", {})

    # Track versions per package name for duplicate detection
    versions_map: dict[str, set[str]] = {}
    max_depth = 0

    for pkg_path, pkg_info in packages.items():
        if not pkg_path:
            continue  # root package entry

        # Calculate depth from nested node_modules path
        # e.g. "node_modules/a/node_modules/b" -> depth 2
        parts = pkg_path.split("node_modules/")
        depth = len(parts) - 1
        max_depth = max(max_depth, depth)

        # Extract package name from path
        name_part = parts[-1] if parts else pkg_path
        # Handle scoped packages: @scope/name
        name = name_part.rstrip("/")
        version = pkg_info.get("version", "unknown")

        if name:
            versions_map.setdefault(name, set()).add(version)

    report.transitive_count = len(versions_map)
    report.max_tree_depth = max_depth

    # Find duplicates (multiple versions of same package)
    for name, versions in sorted(versions_map.items()):
        if len(versions) > 1:
            report.duplicates.append(DuplicateDep(
                name=name, versions=sorted(versions),
            ))


def _parse_node_lock_v1(lock_data: dict, report: DependencyHealthReport) -> None:
    """Parse lockfileVersion 1 (dependencies key with nested structure)."""
    dependencies = lock_data.get("dependencies", {})
    versions_map: dict[str, set[str]] = {}
    max_depth = 0

    def _walk(deps: dict, depth: int) -> None:
        nonlocal max_depth
        max_depth = max(max_depth, depth)
        for name, info in deps.items():
            version = info.get("version", "unknown")
            versions_map.setdefault(name, set()).add(version)
            # Recurse into nested dependencies
            nested = info.get("dependencies", {})
            if nested:
                _walk(nested, depth + 1)

    _walk(dependencies, 1)

    report.transitive_count = len(versions_map)
    report.max_tree_depth = max_depth

    for name, versions in sorted(versions_map.items()):
        if len(versions) > 1:
            report.duplicates.append(DuplicateDep(
                name=name, versions=sorted(versions),
            ))


def _check_node_licenses(
    root: Path, pkg_data: dict, report: DependencyHealthReport,
) -> None:
    """Check for license conflicts in node_modules (shallow check)."""
    project_license = pkg_data.get("license", "")
    nm = root / "node_modules"
    if not nm.exists():
        return

    # Sample: only check direct dependencies (not deep crawl)
    all_deps = list(pkg_data.get("dependencies", {}).keys())
    for dep_name in all_deps[:100]:  # cap to avoid slow scans
        dep_pkg = nm / dep_name / "package.json"
        if not dep_pkg.exists():
            # Handle scoped packages
            if dep_name.startswith("@"):
                continue
            continue
        try:
            dep_data = json.loads(dep_pkg.read_text(encoding="utf-8"))
            dep_license = dep_data.get("license", "")
            if isinstance(dep_license, dict):
                dep_license = dep_license.get("type", "")
            dep_license = str(dep_license).strip()

            if dep_license.upper() in {lic.upper() for lic in _COPYLEFT_LICENSES}:
                report.license_conflicts.append(LicenseConflict(
                    package=dep_name,
                    license=dep_license,
                    reason=f"Copyleft license may conflict with project ({project_license or 'unspecified'})",
                ))
        except (json.JSONDecodeError, OSError):
            continue


# ---------------------------------------------------------------------------
# Python analysis
# ---------------------------------------------------------------------------


def _analyze_python(root: Path) -> DependencyHealthReport:
    """Analyze Python dependency health from pyproject.toml / requirements.txt."""
    report = DependencyHealthReport(ecosystem="python")

    direct_deps: dict[str, str] = {}

    # Parse pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        _parse_pyproject(pyproject, direct_deps, report)

    # Parse requirements.txt (additive)
    req_txt = root / "requirements.txt"
    if req_txt.exists():
        _parse_requirements_txt(req_txt, direct_deps, report)

    report.direct_count = len(direct_deps)

    # Check for outdated patterns
    for name, constraint in direct_deps.items():
        _check_outdated_python(name, constraint, report)

    # Python doesn't have a universal lock file with tree info,
    # but we can check for some common lock files
    _parse_python_lock(root, report)

    return report


def _parse_pyproject(
    path: Path, deps: dict[str, str], report: DependencyHealthReport,
) -> None:
    """Extract dependencies from pyproject.toml (simple parser, no toml lib needed)."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        report.warnings.append(f"Failed to read pyproject.toml: {e}")
        return

    # Find [project] dependencies array
    in_deps = False
    in_optional = False
    bracket_depth = 0

    for line in content.splitlines():
        stripped = line.strip()

        # Detect sections
        if stripped == "[project]":
            continue
        if re.match(r"^\[project\.optional-dependencies\]", stripped):
            in_optional = True
            in_deps = False
            continue
        if stripped.startswith("[") and not stripped.startswith("[["):
            in_deps = False
            in_optional = False
            continue

        # Detect dependencies = [ ... ]
        if "dependencies" in stripped and "=" in stripped and not in_optional:
            in_deps = True
            if "[" in stripped:
                bracket_depth += stripped.count("[") - stripped.count("]")
            continue

        if in_deps:
            bracket_depth += stripped.count("[") - stripped.count("]")
            if bracket_depth <= 0:
                in_deps = False
                continue
            # Parse dep line: "package>=1.0.0",
            dep_match = re.match(r'^"([^"]+)"', stripped)
            if dep_match:
                dep_str = dep_match.group(1)
                _parse_dep_string(dep_str, deps)


def _parse_requirements_txt(
    path: Path, deps: dict[str, str], report: DependencyHealthReport,
) -> None:
    """Parse requirements.txt for dependency names and constraints."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        report.warnings.append(f"Failed to read requirements.txt: {e}")
        return

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        _parse_dep_string(line, deps)


def _parse_dep_string(dep_str: str, deps: dict[str, str]) -> None:
    """Parse a PEP 508 dependency string into name + constraint."""
    # Remove extras: package[extra1,extra2]>=1.0
    dep_str = re.sub(r"\[.*?\]", "", dep_str).strip()
    # Split on first version operator
    match = re.match(r"^([a-zA-Z0-9_.-]+)\s*(.*)", dep_str)
    if match:
        name = match.group(1).lower().replace("-", "_")
        constraint = match.group(2).strip().rstrip(",")
        if name not in deps:
            deps[name] = constraint


def _check_outdated_python(
    name: str, constraint: str, report: DependencyHealthReport,
) -> None:
    """Flag Python deps pinned to == with very old-looking versions."""
    if not constraint:
        return
    # Flag exact pins to 0.x versions
    match = re.match(r"^==\s*0\.\d+", constraint)
    if match:
        report.outdated_hints.append(OutdatedDep(
            name=name, current="0.x", constraint=constraint,
        ))


def _parse_python_lock(root: Path, report: DependencyHealthReport) -> None:
    """Try to extract transitive dep info from Python lock files."""
    # uv.lock
    uv_lock = root / "uv.lock"
    if uv_lock.exists():
        _parse_uv_lock(uv_lock, report)
        return

    # poetry.lock
    poetry_lock = root / "poetry.lock"
    if poetry_lock.exists():
        _parse_poetry_lock(poetry_lock, report)
        return

    # pip-tools requirements (compiled output)
    compiled = root / "requirements.lock"
    if compiled.exists():
        _parse_flat_lock(compiled, report)
        return

    report.warnings.append(
        "No lock file found (uv.lock, poetry.lock) — transitive analysis limited"
    )


def _parse_uv_lock(path: Path, report: DependencyHealthReport) -> None:
    """Parse uv.lock (TOML-like) for package count and duplicate detection."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return

    versions_map: dict[str, set[str]] = {}
    current_name = ""

    for line in content.splitlines():
        stripped = line.strip()
        name_match = re.match(r'^name\s*=\s*"([^"]+)"', stripped)
        if name_match:
            current_name = name_match.group(1).lower().replace("-", "_")
        version_match = re.match(r'^version\s*=\s*"([^"]+)"', stripped)
        if version_match and current_name:
            versions_map.setdefault(current_name, set()).add(version_match.group(1))

    report.transitive_count = len(versions_map)
    # Estimate depth — Python deps are generally flatter
    report.max_tree_depth = min(3, max(1, len(versions_map) // 20))

    for name, versions in sorted(versions_map.items()):
        if len(versions) > 1:
            report.duplicates.append(DuplicateDep(
                name=name, versions=sorted(versions),
            ))


def _parse_poetry_lock(path: Path, report: DependencyHealthReport) -> None:
    """Parse poetry.lock for package count."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return

    versions_map: dict[str, set[str]] = {}
    current_name = ""

    for line in content.splitlines():
        stripped = line.strip()
        name_match = re.match(r'^name\s*=\s*"([^"]+)"', stripped)
        if name_match:
            current_name = name_match.group(1).lower().replace("-", "_")
        version_match = re.match(r'^version\s*=\s*"([^"]+)"', stripped)
        if version_match and current_name:
            versions_map.setdefault(current_name, set()).add(version_match.group(1))

    report.transitive_count = len(versions_map)
    report.max_tree_depth = min(3, max(1, len(versions_map) // 20))

    for name, versions in sorted(versions_map.items()):
        if len(versions) > 1:
            report.duplicates.append(DuplicateDep(
                name=name, versions=sorted(versions),
            ))


def _parse_flat_lock(path: Path, report: DependencyHealthReport) -> None:
    """Parse a flat requirements-style lock file."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return

    count = 0
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("-"):
            count += 1

    report.transitive_count = count
    report.max_tree_depth = min(3, max(1, count // 20))
