"""Parsers for common coverage report formats.

Each parser reads a specific format and returns a CoverageReport
with the unified internal model.
"""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

from .model import CoverageFile, CoverageReport

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cobertura XML
# ---------------------------------------------------------------------------


def parse_cobertura(path: str | Path) -> CoverageReport:
    """Parse a Cobertura XML coverage report.

    Cobertura XML is produced by pytest-cov, Istanbul (JS), and Java tools.
    """
    path = Path(path)
    tree = ET.parse(path)
    root = tree.getroot()

    files: list[CoverageFile] = []

    for pkg in root.iter("package"):
        for cls in pkg.iter("class"):
            filename = cls.attrib.get("filename", "")
            line_rate = float(cls.attrib.get("line-rate", "0"))
            branch_rate_str = cls.attrib.get("branch-rate")
            branch_rate = float(branch_rate_str) if branch_rate_str is not None else None

            lines = cls.find("lines")
            lines_covered = 0
            lines_total = 0
            branches_covered = 0
            branches_total = 0

            if lines is not None:
                for line in lines.iter("line"):
                    lines_total += 1
                    hits = int(line.attrib.get("hits", "0"))
                    if hits > 0:
                        lines_covered += 1

                    if line.attrib.get("branch") == "true":
                        cond = line.attrib.get("condition-coverage", "")
                        if cond:
                            # Format: "75% (3/4)"
                            _parse_condition_coverage(cond, branches_covered_ref=[0], branches_total_ref=[0])
                            try:
                                frac = cond.split("(")[1].rstrip(")")
                                covered, total = frac.split("/")
                                branches_covered += int(covered)
                                branches_total += int(total)
                            except (IndexError, ValueError):
                                pass

            files.append(CoverageFile(
                path=filename,
                line_rate=line_rate,
                branch_rate=branch_rate,
                lines_covered=lines_covered,
                lines_total=lines_total,
                branches_covered=branches_covered,
                branches_total=branches_total,
            ))

    return CoverageReport(
        source_format="cobertura",
        source_file=str(path),
        files=files,
    )


def _parse_condition_coverage(cond: str, branches_covered_ref: list, branches_total_ref: list) -> None:
    """Parse Cobertura condition-coverage string like '75% (3/4)'."""
    try:
        frac = cond.split("(")[1].rstrip(")")
        covered, total = frac.split("/")
        branches_covered_ref[0] = int(covered)
        branches_total_ref[0] = int(total)
    except (IndexError, ValueError):
        pass


# ---------------------------------------------------------------------------
# lcov
# ---------------------------------------------------------------------------


def parse_lcov(path: str | Path) -> CoverageReport:
    """Parse an lcov.info coverage report.

    lcov format uses record markers: SF (source file), DA (line data),
    BRDA (branch data), FNF/FNH (functions found/hit), LF/LH (lines found/hit).
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")

    files: list[CoverageFile] = []
    current_file: str | None = None
    lines_covered = 0
    lines_total = 0
    branches_covered = 0
    branches_total = 0
    functions_covered = 0
    functions_total = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if line.startswith("SF:"):
            current_file = line[3:]
            lines_covered = 0
            lines_total = 0
            branches_covered = 0
            branches_total = 0
            functions_covered = 0
            functions_total = 0

        elif line.startswith("LH:"):
            lines_covered = int(line[3:])
        elif line.startswith("LF:"):
            lines_total = int(line[3:])
        elif line.startswith("BRH:"):
            branches_covered = int(line[4:])
        elif line.startswith("BRF:"):
            branches_total = int(line[4:])
        elif line.startswith("FNH:"):
            functions_covered = int(line[4:])
        elif line.startswith("FNF:"):
            functions_total = int(line[4:])

        elif line == "end_of_record" and current_file is not None:
            line_rate = lines_covered / lines_total if lines_total > 0 else 0.0
            branch_rate = (branches_covered / branches_total) if branches_total > 0 else None
            function_rate = (functions_covered / functions_total) if functions_total > 0 else None

            files.append(CoverageFile(
                path=current_file,
                line_rate=line_rate,
                branch_rate=branch_rate,
                function_rate=function_rate,
                lines_covered=lines_covered,
                lines_total=lines_total,
                branches_covered=branches_covered,
                branches_total=branches_total,
                functions_covered=functions_covered,
                functions_total=functions_total,
            ))
            current_file = None

    return CoverageReport(
        source_format="lcov",
        source_file=str(path),
        files=files,
    )


# ---------------------------------------------------------------------------
# coverage.py JSON
# ---------------------------------------------------------------------------


def parse_coverage_py_json(path: str | Path) -> CoverageReport:
    """Parse a coverage.py JSON report (``coverage json`` output).

    The JSON format contains per-file executed/missing line numbers.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    files: list[CoverageFile] = []

    file_data = data.get("files", {})
    for filename, info in file_data.items():
        summary = info.get("summary", {})
        lines_covered = summary.get("covered_lines", 0)
        lines_total = lines_covered + summary.get("missing_lines", 0)
        line_rate = summary.get("percent_covered", 0.0) / 100.0

        branches_covered = summary.get("covered_branches", 0)
        branches_total = branches_covered + summary.get("missing_branches", 0)
        branch_rate = (branches_covered / branches_total) if branches_total > 0 else None

        files.append(CoverageFile(
            path=filename,
            line_rate=line_rate,
            branch_rate=branch_rate,
            lines_covered=lines_covered,
            lines_total=lines_total,
            branches_covered=branches_covered,
            branches_total=branches_total,
        ))

    return CoverageReport(
        source_format="coverage_py",
        source_file=str(path),
        files=files,
    )


# ---------------------------------------------------------------------------
# JaCoCo XML
# ---------------------------------------------------------------------------


def parse_jacoco(path: str | Path) -> CoverageReport:
    """Parse a JaCoCo XML coverage report.

    JaCoCo is the standard Java/Kotlin coverage tool. Its XML report
    contains counter elements with type LINE, BRANCH, METHOD, etc.
    """
    path = Path(path)
    tree = ET.parse(path)
    root = tree.getroot()

    files: list[CoverageFile] = []

    for pkg in root.iter("package"):
        pkg_name = pkg.attrib.get("name", "").replace("/", ".")
        for src in pkg.iter("sourcefile"):
            filename = src.attrib.get("name", "")
            full_path = f"{pkg_name.replace('.', '/')}/{filename}" if pkg_name else filename

            lines_covered = 0
            lines_total = 0
            branches_covered = 0
            branches_total = 0
            functions_covered = 0
            functions_total = 0

            for counter in src.iter("counter"):
                ctype = counter.attrib.get("type", "")
                missed = int(counter.attrib.get("missed", "0"))
                covered = int(counter.attrib.get("covered", "0"))

                if ctype == "LINE":
                    lines_covered = covered
                    lines_total = covered + missed
                elif ctype == "BRANCH":
                    branches_covered = covered
                    branches_total = covered + missed
                elif ctype == "METHOD":
                    functions_covered = covered
                    functions_total = covered + missed

            line_rate = lines_covered / lines_total if lines_total > 0 else 0.0
            branch_rate = (branches_covered / branches_total) if branches_total > 0 else None
            function_rate = (functions_covered / functions_total) if functions_total > 0 else None

            files.append(CoverageFile(
                path=full_path,
                line_rate=line_rate,
                branch_rate=branch_rate,
                function_rate=function_rate,
                lines_covered=lines_covered,
                lines_total=lines_total,
                branches_covered=branches_covered,
                branches_total=branches_total,
                functions_covered=functions_covered,
                functions_total=functions_total,
            ))

    return CoverageReport(
        source_format="jacoco",
        source_file=str(path),
        files=files,
    )
