"""Coverage report unification — parse any format into a unified model and render as docs.

Supported formats:
- Cobertura XML (Java, Python via pytest-cov, JS via Istanbul)
- lcov.info (C/C++, JS, Go)
- coverage.py JSON (Python)
- JaCoCo XML (Java/Kotlin)

Usage:
    from repoforge.coverage import auto_detect_and_parse, render_coverage_markdown

    reports = auto_detect_and_parse("/path/to/project")
    markdown = render_coverage_markdown(reports)
"""

from .detector import auto_detect_and_parse, detect_coverage_files
from .model import CoverageFile, CoverageReport
from .parsers import (
    parse_cobertura,
    parse_coverage_py_json,
    parse_jacoco,
    parse_lcov,
)
from .renderer import render_coverage_markdown

__all__ = [
    "CoverageFile",
    "CoverageReport",
    "parse_cobertura",
    "parse_lcov",
    "parse_coverage_py_json",
    "parse_jacoco",
    "auto_detect_and_parse",
    "detect_coverage_files",
    "render_coverage_markdown",
]
