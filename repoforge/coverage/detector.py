"""Auto-detect coverage files in a project and parse them.

Walks the project directory looking for known coverage file patterns,
identifies the format, and delegates to the appropriate parser.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .model import CoverageReport
from .parsers import (
    parse_cobertura,
    parse_coverage_py_json,
    parse_jacoco,
    parse_lcov,
)

logger = logging.getLogger(__name__)

# (glob pattern, parser function, format name)
_DETECTION_RULES: list[tuple[str, str]] = [
    ("coverage.xml", "cobertura"),
    ("cobertura.xml", "cobertura"),
    ("cobertura-coverage.xml", "cobertura"),
    ("lcov.info", "lcov"),
    ("coverage/lcov.info", "lcov"),
    ("coverage.json", "coverage_py"),
    ("jacoco.xml", "jacoco"),
    ("target/site/jacoco/jacoco.xml", "jacoco"),
    ("build/reports/jacoco/test/jacocoTestReport.xml", "jacoco"),
]

_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", ".tox",
}

_PARSERS = {
    "cobertura": parse_cobertura,
    "lcov": parse_lcov,
    "coverage_py": parse_coverage_py_json,
    "jacoco": parse_jacoco,
}


def detect_coverage_files(root: str | Path) -> list[tuple[Path, str]]:
    """Find coverage files in the project directory.

    Returns a list of (path, format_name) tuples.
    """
    root = Path(root).resolve()
    found: list[tuple[Path, str]] = []

    # Check known fixed paths first
    for pattern, fmt in _DETECTION_RULES:
        candidate = root / pattern
        if candidate.is_file() and _validate_format(candidate, fmt):
            found.append((candidate, fmt))

    # Walk for common coverage filenames in subdirectories (max depth 4)
    _coverage_filenames = {
        "coverage.xml": "cobertura",
        "cobertura.xml": "cobertura",
        "lcov.info": "lcov",
        "coverage.json": "coverage_py",
        "jacoco.xml": "jacoco",
    }

    for child in _walk_limited(root, max_depth=4):
        if child.name in _coverage_filenames:
            candidate_fmt = _coverage_filenames[child.name]
            # Validate it's actually the right format before adding
            if _validate_format(child, candidate_fmt):
                entry = (child, candidate_fmt)
                if entry not in found:
                    found.append(entry)

    return found


def _walk_limited(root: Path, max_depth: int) -> list[Path]:
    """Walk directory tree with depth limit, skipping irrelevant dirs."""
    results: list[Path] = []
    _walk_recursive(root, 0, max_depth, results)
    return results


def _walk_recursive(current: Path, depth: int, max_depth: int, results: list[Path]) -> None:
    if depth > max_depth:
        return
    try:
        for entry in sorted(current.iterdir()):
            if entry.is_file():
                results.append(entry)
            elif entry.is_dir() and entry.name not in _SKIP_DIRS:
                _walk_recursive(entry, depth + 1, max_depth, results)
    except PermissionError:
        pass


def _validate_format(path: Path, expected_format: str) -> bool:
    """Quick validation that the file matches the expected format."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:500]
    except OSError:
        return False

    if expected_format == "cobertura":
        return "<coverage" in head or "<cobertura" in head
    elif expected_format == "lcov":
        return head.strip().startswith("TN:") or head.strip().startswith("SF:")
    elif expected_format == "coverage_py":
        return '"meta"' in head and '"files"' in head
    elif expected_format == "jacoco":
        return "<report" in head or "jacoco" in head.lower()
    return False


def auto_detect_and_parse(root: str | Path) -> list[CoverageReport]:
    """Detect coverage files in a project and parse all of them.

    Returns a list of CoverageReport objects, one per detected file.
    """
    root = Path(root).resolve()
    detected = detect_coverage_files(root)

    reports: list[CoverageReport] = []
    for path, fmt in detected:
        parser = _PARSERS.get(fmt)
        if parser is None:
            logger.warning("No parser for format %r at %s", fmt, path)
            continue
        try:
            report = parser(path)
            reports.append(report)
            logger.debug("Parsed %s coverage from %s (%d files)", fmt, path, len(report.files))
        except Exception as e:
            logger.warning("Failed to parse %s: %s", path, e)

    return reports
